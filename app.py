import os, json, shutil, io, zipfile, uuid, re, time, threading
from flask import Flask, render_template, request, jsonify, send_file, session
from werkzeug.utils import secure_filename
from PIL import Image
import piexif, requests as req
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'crazypro-rfa-2026')
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

UPLOAD_BASE = '/tmp/cp_uploads'
MODELS_FILE = os.environ.get('CRAZYPRO_MODELS_FILE') or os.path.join(os.path.expanduser('~'), '.crazypro_rfa', 'models.json')
LEGACY_MODELS_FILE = '/tmp/cp_models.json'
RETENTION_HOURS = float(os.environ.get('CRAZYPRO_RETENTION_HOURS', '24'))
_contact = os.environ.get('CRAZYPRO_CONTACT', '').strip()
NOMINATIM_UA = 'CrazyPro-RFA/1.0' + (f' ({_contact})' if _contact else '')
SUPPORTED = {'.jpg','.jpeg','.tiff','.tif','.dng','.nef','.raf','.crw','.raw','.png'}

try:
    from icon_data import ICON_B64
except:
    ICON_B64 = ''

def get_sid():
    if 'sid' not in session:
        session['sid'] = str(uuid.uuid4())
    return session['sid']

def user_dir(sid):
    d = os.path.join(UPLOAD_BASE, sid)
    os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(d, 'output'), exist_ok=True)
    return d

def cleanup_old_uploads(keep_sid=None):
    limit=time.time()-RETENTION_HOURS*3600
    try: names=os.listdir(UPLOAD_BASE)
    except FileNotFoundError: return
    for name in names:
        p=os.path.join(UPLOAD_BASE,name)
        if name==keep_sid or not os.path.isdir(p): continue
        try:
            newest=max(os.path.getmtime(p), os.path.getmtime(os.path.join(p,'output')) if os.path.isdir(os.path.join(p,'output')) else 0)
            if newest<limit: shutil.rmtree(p,ignore_errors=True)
        except OSError: pass

_nom_lock=threading.Lock(); _nom_last=[0.0]; _nom_cache={}
def nominatim_get(path, params):
    key=(path,tuple(sorted(params.items())))
    if key in _nom_cache: return _nom_cache[key]
    with _nom_lock:
        wait=1.1-(time.time()-_nom_last[0])
        if wait>0: time.sleep(wait)
        r=req.get('https://nominatim.openstreetmap.org/'+path,params=params,
                  headers={'User-Agent':NOMINATIM_UA},timeout=8)
        _nom_last[0]=time.time()
    if getattr(r,'status_code',200)!=200: raise RuntimeError(f'HTTP {r.status_code}')
    data=r.json()
    if len(_nom_cache)>200: _nom_cache.clear()
    _nom_cache[key]=data
    return data

EXIF_DATE_RE=re.compile(r'^\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}$')
def valid_exif_date(v):
    return bool(v) and bool(EXIF_DATE_RE.match(v)) and not v.startswith('0000')

def load_json(p):
    try: return json.load(open(p))
    except: return {}

def save_json(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)

def load_models():
    if not os.path.exists(MODELS_FILE) and os.path.exists(LEGACY_MODELS_FILE):
        return load_json(LEGACY_MODELS_FILE)
    return load_json(MODELS_FILE)

def deg_to_dms(deg):
    deg=abs(float(deg)); d=int(deg); m=int((deg-d)*60); s=round(((deg-d)*60-m)*60,4)
    return [(d,1),(m,1),(int(s*10000),10000)]

def dms_to_deg(dms):
    try: return dms[0][0]/dms[0][1]+dms[1][0]/dms[1][1]/60+dms[2][0]/dms[2][1]/3600
    except: return 0

def get_exif(path):
    info={k:'' for k in ['desc','artist','copyright','date','city','state','country','address','street','number','complement','neighborhood','website','email','mainCategory','categories','keywords']}
    info.update({'lat':None,'lon':None,'alt':None,'rating':0,'width':0,'height':0})
    try:
        img=Image.open(path); info['width'],info['height']=img.size
        raw=img.info.get('exif',b'')
        if not raw: return info
        exif=piexif.load(raw); gps=exif.get('GPS',{}); z=exif.get('0th',{})
        if piexif.GPSIFD.GPSLatitude in gps:
            lat=dms_to_deg(gps[piexif.GPSIFD.GPSLatitude])
            ref=gps.get(piexif.GPSIFD.GPSLatitudeRef,b'N')
            if isinstance(ref,bytes): ref=ref.decode()
            info['lat']=-lat if ref=='S' else lat
        if piexif.GPSIFD.GPSLongitude in gps:
            lon=dms_to_deg(gps[piexif.GPSIFD.GPSLongitude])
            ref=gps.get(piexif.GPSIFD.GPSLongitudeRef,b'E')
            if isinstance(ref,bytes): ref=ref.decode()
            info['lon']=-lon if ref=='W' else lon
        if piexif.GPSIFD.GPSAltitude in gps:
            a=gps[piexif.GPSIFD.GPSAltitude]; info['alt']=round(a[0]/a[1],2)
        for tag,key in [(piexif.ImageIFD.ImageDescription,'desc'),(piexif.ImageIFD.Artist,'artist'),
                        (piexif.ImageIFD.Copyright,'copyright'),(piexif.ImageIFD.DateTime,'date')]:
            if tag in z: info[key]=z[tag].decode(errors='ignore').strip('\x00')
    except: pass
    return info

def esc(s):
    if not s: return ''
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

def build_full_xmp(meta):
    desc=esc(meta.get('desc','')); artist=esc(meta.get('artist',''))
    copyright=esc(meta.get('copyright',''))
    # dc:title is separate from description — use dedicated title field or first 80 chars of desc
    title=esc(meta.get('title','') or (meta.get('desc','')[:80] if meta.get('desc') else ''))
    city=esc(meta.get('city','')); state=esc(meta.get('state',''))
    country=esc(meta.get('country','Brasil')); address=esc(meta.get('address',''))
    cep=esc(str(meta.get('cep','')).replace('-','')); website=esc(meta.get('website',''))
    email=esc(meta.get('email','')); phone=esc(meta.get('phone',''))
    category=esc(meta.get('mainCategory','')); rating=int(meta.get('rating') or 0)
    # Social network as AuthorsPosition (like GeoSetter uses WhatsApp/Instagram etc)
    authors_position=esc(meta.get('social_main',''))
    try:
        import json as _j
        socials=_j.loads(meta.get('social','[]'))
        if socials: authors_position=esc(socials[0].get('net',''))
    except: pass
    lat=meta.get('lat'); lon=meta.get('lon')
    kw_raw=meta.get('keywords','')
    keywords=[esc(k.strip()) for k in kw_raw.split(',') if k.strip()] if kw_raw else []
    cat_raw=meta.get('categories','')
    subcats=[esc(c.strip()) for c in cat_raw.split(',') if c.strip()] if cat_raw else []
    kw_items='\n'.join(f'    <rdf:li>{k}</rdf:li>' for k in keywords)
    kw_block=f'  <dc:subject>\n   <rdf:Bag>\n{kw_items}\n   </rdf:Bag>\n  </dc:subject>' if keywords else ''
    sub_items='\n'.join(f'    <rdf:li>{c}</rdf:li>' for c in subcats)
    sub_block=f'  <photoshop:SupplementalCategories>\n   <rdf:Bag>\n{sub_items}\n   </rdf:Bag>\n  </photoshop:SupplementalCategories>' if subcats else ''

    gps_block=''
    if lat and lon:
        try:
            flat=float(lat); flon=float(lon)
            flat_d=int(abs(flat)); flat_m=(abs(flat)-flat_d)*60
            flon_d=int(abs(flon)); flon_m=(abs(flon)-flon_d)*60
            lat_ref='S' if flat<0 else 'N'; lon_ref='W' if flon<0 else 'E'
            gps_block=(f"  <exif:GPSLatitude>{flat_d},{flat_m:.6f}{lat_ref}</exif:GPSLatitude>\n"
                       f"  <exif:GPSLongitude>{flon_d},{flon_m:.6f}{lon_ref}</exif:GPSLongitude>\n"
                       "  <exif:GPSMapDatum>WGS-84</exif:GPSMapDatum>\n"
                       "  <exif:GPSVersionID>2.2.0.0</exif:GPSVersionID>\n")
            if meta.get('alt') not in (None,''):
                av=float(meta.get('alt'))
                gps_block+=(f"  <exif:GPSAltitude>{int(round(abs(av)))}/1</exif:GPSAltitude>\n"
                            f"  <exif:GPSAltitudeRef>{0 if av>=0 else 1}</exif:GPSAltitudeRef>\n")
        except: gps_block=''

    ms_rating=99 if rating==5 else(75 if rating==4 else(50 if rating==3 else(25 if rating==2 else(1 if rating==1 else 0))))
    country_code=country[:3].upper() if country else 'BRA'

    # photoshop:DateCreated — ISO 8601 form of the EXIF date
    date_raw=meta.get('date','')
    photoshop_date=''
    try:
        if date_raw:
            parts=date_raw.replace(' ',':').split(':')
            photoshop_date=f'{parts[0]}-{parts[1]}-{parts[2]}T{parts[3]}:{parts[4]}:{parts[5]}'
    except: pass

    now_iso=datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    exif_dates=(f"  <exif:DateTimeOriginal>{photoshop_date}</exif:DateTimeOriginal>\n"
                f"  <exif:DateTimeDigitized>{photoshop_date}</exif:DateTimeDigitized>\n") if photoshop_date else ''
    ps_date=f"  <photoshop:DateCreated>{photoshop_date}</photoshop:DateCreated>\n" if photoshop_date else ''
    xmp_create=f"  <xmp:CreateDate>{photoshop_date}</xmp:CreateDate>\n" if photoshop_date else ''

    # xmpMM document IDs — unique per export
    import uuid as _uuid
    doc_id=f'xmp.did:{_uuid.uuid4()}'
    inst_id=f'xmp.iid:{_uuid.uuid4()}'

    return f"""<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>
<x:xmpmeta xmlns:x='adobe:ns:meta/' x:xmptk='Image::ExifTool 10.96'>
<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>

 <rdf:Description rdf:about=''
  xmlns:Iptc4xmpCore='http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/'>
  <Iptc4xmpCore:CountryCode>{country_code}</Iptc4xmpCore:CountryCode>
  <Iptc4xmpCore:Location>{address}</Iptc4xmpCore:Location>
  <Iptc4xmpCore:CreatorContactInfo rdf:parseType='Resource'>
   <Iptc4xmpCore:CiAdrCity>{city}</Iptc4xmpCore:CiAdrCity>
   <Iptc4xmpCore:CiAdrCtry>{country}</Iptc4xmpCore:CiAdrCtry>
   <Iptc4xmpCore:CiAdrExtadr>{address}</Iptc4xmpCore:CiAdrExtadr>
   <Iptc4xmpCore:CiAdrPcode>{cep}</Iptc4xmpCore:CiAdrPcode>
   <Iptc4xmpCore:CiAdrRegion>{state}</Iptc4xmpCore:CiAdrRegion>
   <Iptc4xmpCore:CiEmailWork>{email}</Iptc4xmpCore:CiEmailWork>
   <Iptc4xmpCore:CiTelWork>{phone}</Iptc4xmpCore:CiTelWork>
   <Iptc4xmpCore:CiUrlWork>{website}</Iptc4xmpCore:CiUrlWork>
  </Iptc4xmpCore:CreatorContactInfo>
 </rdf:Description>

 <rdf:Description rdf:about=''
  xmlns:MicrosoftPhoto='http://ns.microsoft.com/photo/1.0'>
  <MicrosoftPhoto:Rating>{ms_rating}</MicrosoftPhoto:Rating>
 </rdf:Description>

 <rdf:Description rdf:about=''
  xmlns:dc='http://purl.org/dc/elements/1.1/'>
  <dc:creator><rdf:Seq><rdf:li>{artist}</rdf:li></rdf:Seq></dc:creator>
  <dc:description><rdf:Alt><rdf:li xml:lang='x-default'>{desc}</rdf:li></rdf:Alt></dc:description>
  <dc:rights><rdf:Alt><rdf:li xml:lang='x-default'>{copyright}</rdf:li></rdf:Alt></dc:rights>
  <dc:title><rdf:Alt><rdf:li xml:lang='x-default'>{title}</rdf:li></rdf:Alt></dc:title>
{kw_block}
 </rdf:Description>

 <rdf:Description rdf:about=''
  xmlns:exif='http://ns.adobe.com/exif/1.0/'>
{exif_dates}{gps_block} </rdf:Description>

 <rdf:Description rdf:about=''
  xmlns:photoshop='http://ns.adobe.com/photoshop/1.0/'>
  <photoshop:AuthorsPosition>{authors_position}</photoshop:AuthorsPosition>
  <photoshop:CaptionWriter>{artist}</photoshop:CaptionWriter>
  <photoshop:Category>{category}</photoshop:Category>
  <photoshop:City>{city}</photoshop:City>
  <photoshop:Country>{country}</photoshop:Country>
  <photoshop:Credit>{artist}</photoshop:Credit>
{ps_date}  <photoshop:Headline>{title}</photoshop:Headline>
  <photoshop:Instructions>{desc}</photoshop:Instructions>
  <photoshop:Source>{artist}</photoshop:Source>
  <photoshop:State>{state}</photoshop:State>
{sub_block}
 </rdf:Description>

 <rdf:Description rdf:about=''
  xmlns:tiff='http://ns.adobe.com/tiff/1.0/'>
  <tiff:Artist>{artist}</tiff:Artist>
 </rdf:Description>

 <rdf:Description rdf:about=''
  xmlns:xmp='http://ns.adobe.com/xap/1.0/'>
  <xmp:Rating>{rating}</xmp:Rating>
  <xmp:BaseURL>{website}</xmp:BaseURL>
  <xmp:CreatorTool>CrazyPro RFA</xmp:CreatorTool>
{xmp_create}  <xmp:ModifyDate>{now_iso}</xmp:ModifyDate>
  <xmp:MetadataDate>{now_iso}</xmp:MetadataDate>
 </rdf:Description>

 <rdf:Description rdf:about=''
  xmlns:xmpRights='http://ns.adobe.com/xap/1.0/rights/'>
  <xmpRights:Marked>True</xmpRights:Marked>
  <xmpRights:WebStatement>{website}</xmpRights:WebStatement>
  <xmpRights:UsageTerms><rdf:Alt><rdf:li xml:lang='x-default'>{copyright}</rdf:li></rdf:Alt></xmpRights:UsageTerms>
 </rdf:Description>

 <rdf:Description rdf:about=''
  xmlns:xmpMM='http://ns.adobe.com/xap/1.0/mm/'>
  <xmpMM:DocumentID>{doc_id}</xmpMM:DocumentID>
  <xmpMM:InstanceID>{inst_id}</xmpMM:InstanceID>
 </rdf:Description>

</rdf:RDF>
</x:xmpmeta>
{' '*100}
<?xpacket end='w'?>"""

def inject_xmp_full(jpeg_bytes, meta):
    try:
        xmp_bytes=build_full_xmp(meta).encode('utf-8')
        result=bytearray(jpeg_bytes)
        i=2
        while i < len(result)-4:
            if result[i]==0xFF:
                marker=result[i+1]
                if marker==0xE1:
                    seg_len=(result[i+2]<<8)|result[i+3]
                    seg_data=result[i+4:i+4+seg_len-2]
                    if seg_data[:29]==b'http://ns.adobe.com/xap/1.0/\x00':
                        del result[i:i+2+seg_len]; continue
                    i+=2+seg_len
                elif marker in(0xD8,0xD9,0xDA): break
                else:
                    try: seg_len=(result[i+2]<<8)|result[i+3]; i+=2+seg_len
                    except: break
            else: i+=1
        ns=b'http://ns.adobe.com/xap/1.0/\x00'
        payload=ns+xmp_bytes
        seg=bytes([0xFF,0xE1])+((len(payload)+2).to_bytes(2,'big'))+payload
        return bytes(result[:2])+seg+bytes(result[2:])
    except Exception as e:
        print(f"inject_xmp error: {e}"); return jpeg_bytes

def build_iptc(meta):
    """IPTC-IIM (APP13 / Photoshop 3.0), UTF-8, como o GeoSetter grava."""
    import struct
    def rec(ds, val):
        b=str(val).encode('utf-8')[:2000]
        return b'\x1c\x02'+bytes([ds])+struct.pack('>H',len(b))+b
    date_raw=meta.get('date','') or ''
    out=b'\x1c\x01\x5a\x00\x03\x1b%G'  # CodedCharacterSet = UTF-8
    title=meta.get('title') or (meta.get('desc') or '')[:80]
    social=''
    try:
        socials=json.loads(meta.get('social') or '[]')
        if socials: social=socials[0].get('net','')
    except: pass
    fields=[(5,title),(40,meta.get('desc')),(80,meta.get('artist')),(85,social),(90,meta.get('city')),
            (95,meta.get('state')),(101,meta.get('country')),(105,title),(110,meta.get('artist')),
            (115,meta.get('artist')),(116,meta.get('copyright')),(120,meta.get('desc')),(122,meta.get('artist'))]
    for ds,val in fields:
        if val: out+=rec(ds,val)
    try:
        p=date_raw.replace(' ',':').split(':')
        out+=rec(55,f'{p[0]}{p[1]}{p[2]}')+rec(60,f'{p[3]}{p[4]}{p[5]}')
    except: pass
    for c in (meta.get('categories') or '').split(','):
        if c.strip(): out+=rec(20,c.strip())
    for k in (meta.get('keywords') or '').split(','):
        if k.strip(): out+=rec(25,k.strip())
    if len(out)%2: out+=b'\x00'
    return b'8BIM\x04\x04\x00\x00'+struct.pack('>I',len(out))+out

def inject_iptc(jpeg_bytes, meta):
    try:
        block=b'Photoshop 3.0\x00'+build_iptc(meta)
        seg=b'\xff\xed'+(len(block)+2).to_bytes(2,'big')+block
        return jpeg_bytes[:2]+seg+jpeg_bytes[2:]
    except Exception as e:
        print(f"inject_iptc error: {e}"); return jpeg_bytes

def resize_crop_center(img, w, h):
    """Resize image to exact w×h using center crop (no distortion, no borders)."""
    from PIL import ImageOps
    return ImageOps.fit(img, (w, h), Image.LANCZOS)

def write_exif(src, meta, out_path):
    try:
        img=Image.open(src)
        src_exif_raw=img.info.get('exif',b'')
        if img.mode not in('RGB','L'): img=img.convert('RGB')

        # Resize for Google Meu Negócio if requested
        if meta.get('gmn_resize') == '1':
            try:
                tw = int(meta.get('gmn_w', 1080))
                th = int(meta.get('gmn_h', 1080))
                img = resize_crop_center(img, tw, th)
            except Exception as e:
                print(f"resize warning: {e}")

        try:
            exif=piexif.load(src_exif_raw) if src_exif_raw else {'0th':{},'Exif':{},'GPS':{},'1st':{}}
        except: exif={'0th':{},'Exif':{},'GPS':{},'1st':{}}
        z,gps,exif_ifd=exif.get('0th',{}),exif.get('GPS',{}),exif.get('Exif',{})

        # Data de captura: preserva a original da foto; a data do formulário só entra
        # em fotos sem data, ou quando o usuário pedir para substituir (date_force).
        def _dec(v): return v.decode(errors='ignore').strip('\x00').strip() if isinstance(v,bytes) else ''
        orig_date=''
        for _ifd,_tag in ((exif_ifd,piexif.ExifIFD.DateTimeOriginal),(exif_ifd,piexif.ExifIFD.DateTimeDigitized),(z,piexif.ImageIFD.DateTime)):
            _v=_dec(_ifd.get(_tag))
            if valid_exif_date(_v): orig_date=_v; break
        form_date=(meta.get('date') or '').strip()
        if form_date and not valid_exif_date(form_date):
            print(f"data ignorada (formato inválido): {form_date!r}"); form_date=''
        force=str(meta.get('date_force',''))=='1'
        eff_date=form_date if (force and form_date) else (orig_date or form_date)
        meta=dict(meta); meta['date']=eff_date
        if eff_date:
            _b=eff_date.encode('utf-8')
            for _ifd,_tag in ((exif_ifd,piexif.ExifIFD.DateTimeOriginal),(exif_ifd,piexif.ExifIFD.DateTimeDigitized),(z,piexif.ImageIFD.DateTime)):
                if force or not valid_exif_date(_dec(_ifd.get(_tag))): _ifd[_tag]=_b
        # dimensões declaradas no EXIF acompanham a imagem final
        if piexif.ExifIFD.PixelXDimension in exif_ifd: exif_ifd[piexif.ExifIFD.PixelXDimension]=img.size[0]
        if piexif.ExifIFD.PixelYDimension in exif_ifd: exif_ifd[piexif.ExifIFD.PixelYDimension]=img.size[1]

        for val,tag in [(meta.get('desc'),piexif.ImageIFD.ImageDescription),
                        (meta.get('artist'),piexif.ImageIFD.Artist),
                        (meta.get('copyright'),piexif.ImageIFD.Copyright)]:
            if val:
                try:
                    encoded = str(val).encode('utf-8')
                    z[tag] = encoded
                except:
                    z[tag] = str(val).encode('latin-1', 'replace')
        # Software tag — authorship trail
        z[piexif.ImageIFD.Software] = b'CrazyPro RFA'
        # Windows Explorer tags (UTF-16LE) + UserComment, como o GeoSetter grava
        def _xp(s): return str(s).encode('utf-16le') + b'\x00\x00'
        kw_str=';'.join(k.strip() for k in (meta.get('keywords') or '').split(',') if k.strip())
        title_val=meta.get('title') or (meta.get('desc') or '')[:80]
        if title_val: z[piexif.ImageIFD.XPTitle]=_xp(title_val)
        if meta.get('desc'):
            z[piexif.ImageIFD.XPComment]=_xp(meta['desc'])
            exif_ifd[piexif.ExifIFD.UserComment]=b'UNICODE\x00'+str(meta['desc']).encode('utf-16le')
        if meta.get('artist'): z[piexif.ImageIFD.XPAuthor]=_xp(meta['artist'])
        if kw_str: z[piexif.ImageIFD.XPKeywords]=_xp(kw_str)
        if meta.get('mainCategory'): z[piexif.ImageIFD.XPSubject]=_xp(meta['mainCategory'])
        lat=meta.get('lat'); lon=meta.get('lon'); alt=meta.get('alt')
        if lat and lon:
            lat,lon=float(lat),float(lon)
            gps[piexif.GPSIFD.GPSVersionID]      = (2,2,0,0)
            gps[piexif.GPSIFD.GPSLatitudeRef]    = b'N' if lat>=0 else b'S'
            gps[piexif.GPSIFD.GPSLatitude]       = deg_to_dms(lat)
            gps[piexif.GPSIFD.GPSLongitudeRef]   = b'E' if lon>=0 else b'W'
            gps[piexif.GPSIFD.GPSLongitude]      = deg_to_dms(lon)
            gps[piexif.GPSIFD.GPSMapDatum]       = b'WGS-84'
        if alt:
            av=float(alt)
            gps[piexif.GPSIFD.GPSAltitude]=(int(abs(av)*100),100)
            gps[piexif.GPSIFD.GPSAltitudeRef]=0 if av>=0 else 1
        exif['0th']=z; exif['GPS']=gps; exif['Exif']=exif_ifd
        buf=io.BytesIO()
        img.save(buf,'JPEG',exif=piexif.dump(exif),quality=int(meta.get('quality',95)),optimize=False,subsampling=0)
        jpeg_bytes=inject_iptc(buf.getvalue(), meta)
        jpeg_bytes=inject_xmp_full(jpeg_bytes, meta)
        with open(out_path,'wb') as f: f.write(jpeg_bytes)
        return True
    except Exception as e:
        print(f"write_exif: {e}"); return False

@app.route('/')
def index():
    return render_template('index.html', icon=ICON_B64)

@app.route('/upload', methods=['POST'])
def upload():
    sid=get_sid(); ud=user_dir(sid)
    cleanup_old_uploads(keep_sid=sid)
    files=request.files.getlist('files'); saved=[]
    for f in files:
        orig_name = f.filename
        ext=os.path.splitext(orig_name)[1].lower()
        if not ext or ext not in SUPPORTED:
            # Try to detect from content type
            ct = f.content_type or ''
            if 'jpeg' in ct or 'jpg' in ct: ext='.jpg'
            elif 'png' in ct: ext='.png'
            else: ext='.jpg'  # default
        if ext not in SUPPORTED: continue
        # Build safe filename preserving original name + correct extension
        safe = secure_filename(orig_name)
        if not safe.lower().endswith(ext):
            safe = os.path.splitext(safe)[0] + ext
        if not safe or safe == ext:
            safe = f'foto_{uuid.uuid4().hex[:8]}{ext}'
        fname = safe
        fpath=os.path.join(ud,fname); f.save(fpath)
        exif_info=get_exif(fpath)
        try:
            img=Image.open(fpath); img.thumbnail((200,200))
            if img.mode not in('RGB','L'): img=img.convert('RGB')
            tp=os.path.join(ud,'thumb_'+fname+'.jpg')
            img.save(tp,'JPEG',quality=70)
            thumb=f'/file/{sid}/thumb_{fname}.jpg'
        except: thumb=None
        saved.append({'name':fname,'orig':f.filename,'thumb':thumb,'exif':exif_info})
    return jsonify({'files':saved,'sid':sid})

@app.route('/file/<sid>/<path:fn>')
def serve_file(sid,fn):
    return send_file(os.path.join(UPLOAD_BASE,sid,fn))

@app.route('/apply', methods=['POST'])
def apply():
    data=request.json; sid=data.get('sid') or get_sid()
    ud=user_dir(sid); out_dir=os.path.join(ud,'output')
    files=data.get('files',[]); meta=data.get('meta',{}); rename=data.get('rename','')
    index=data.get('index',0)
    results=[]
    for i,fname in enumerate(files):
        src=os.path.join(ud,fname)
        if not os.path.exists(src): results.append({'file':fname,'ok':False,'msg':'não encontrado'}); continue
        # Get base name — remove ALL known image extensions safely
        import re
        orig_base = re.sub(r'\.(jpg|jpeg|png|tif|tiff|dng|nef|raf|crw|raw)$', '', fname, flags=re.IGNORECASE)
        # If no extension was removed, use splitext as fallback
        if orig_base == fname:
            orig_base = os.path.splitext(fname)[0]
        global_i=index+i
        if rename:
            base=rename.replace('{n}',str(global_i+1).zfill(3)).replace('{name}',orig_base).replace('{date}',datetime.now().strftime('%Y%m%d'))
        else:
            base=orig_base
        # Always output as .jpg
        out_name=base+'.jpg'
        out_path=os.path.join(out_dir,out_name)
        # Avoid overwrite
        counter=1
        while os.path.exists(out_path) and out_path!=os.path.join(out_dir,orig_base+'.jpg'):
            out_name=f"{base}_{counter}.jpg"; out_path=os.path.join(out_dir,out_name); counter+=1
        ok=write_exif(src,meta,out_path)
        item={'file':fname,'out':out_name,'ok':ok,'sid':sid}
        if ok:
            try:
                item['size']=os.path.getsize(out_path)
                with Image.open(out_path) as _im: item['w'],item['h']=_im.size
            except Exception: pass
        results.append(item)
    return jsonify({'results':results,'sid':sid})

@app.route('/download_all/<sid>')
def download_all(sid):
    out_dir=os.path.join(UPLOAD_BASE,sid,'output')
    if not os.path.exists(out_dir): return 'Nenhum arquivo',404
    # Filtra só os arquivos da rodada atual se informado
    requested=request.args.get('files','')
    if requested:
        files=[f for f in requested.split(',') if f and os.path.exists(os.path.join(out_dir,f))]
    else:
        files=[f for f in os.listdir(out_dir) if f.lower().endswith(('.jpg','.jpeg'))]
    if not files: return 'Pasta vazia — processe as fotos primeiro',404
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(os.path.join(out_dir,f), f)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name='crazypro_fotos.zip', mimetype='application/zip')

@app.route('/list_output/<sid>')
def list_output(sid):
    out_dir=os.path.join(UPLOAD_BASE,sid,'output')
    if not os.path.exists(out_dir): return jsonify([])
    files=[f for f in sorted(os.listdir(out_dir)) if f.lower().endswith(('.jpg','.jpeg'))]
    return jsonify(files)

@app.route('/download_file/<sid>/<fn>')
def download_file(sid,fn):
    p=os.path.join(UPLOAD_BASE,sid,'output',fn)
    if not os.path.exists(p):
        return ('não encontrado',404)
    return send_file(p, as_attachment=True, download_name=fn, mimetype='image/jpeg')

@app.route('/clear', methods=['POST'])
def clear():
    sid=request.json.get('sid') or session.get('sid','')
    if sid:
        ud=os.path.join(UPLOAD_BASE,sid)
        # Clear only uploads, keep output
        for f in os.listdir(ud):
            p=os.path.join(ud,f)
            if os.path.isfile(p): os.remove(p)
    return jsonify({'ok':True})

@app.route('/cep/<cep>')
def busca_cep(cep):
    cep=cep.replace('-','').replace('.','').strip()
    if len(cep)!=8 or not cep.isdigit():
        return jsonify({'erro':True}),400
    # 1) ViaCEP
    try:
        r=req.get(f'https://viacep.com.br/ws/{cep}/json/',timeout=5)
        d=r.json()
        if not d.get('erro'): return jsonify(d)
    except: pass
    # 2) BrasilAPI
    try:
        r=req.get(f'https://brasilapi.com.br/api/cep/v2/{cep}',timeout=5)
        d=r.json()
        if d.get('cep'):
            return jsonify({
                'cep': d.get('cep',''),
                'logradouro': d.get('street',''),
                'complemento': d.get('location',{}).get('place','') if isinstance(d.get('location'),dict) else '',
                'bairro': d.get('neighborhood',''),
                'localidade': d.get('city',''),
                'uf': d.get('state',''),
            })
    except: pass
    # 3) OpenCEP
    try:
        r=req.get(f'https://opencep.com/v1/{cep}',timeout=5)
        d=r.json()
        if d.get('cep'): return jsonify(d)
    except: pass
    return jsonify({'erro':True}),400

@app.route('/geocode')
def geocode():
    q=request.args.get('q','')
    try:
        return jsonify(nominatim_get('search',{'q':q,'format':'json','limit':1}))
    except: return jsonify([]),400

@app.route('/reverse')
def reverse_geocode():
    try:
        lat=float(request.args.get('lat','')); lon=float(request.args.get('lon',''))
        if not(-90<=lat<=90 and -180<=lon<=180): raise ValueError
    except (TypeError,ValueError):
        return jsonify({'erro':'coordenadas inválidas'}),400
    try:
        d=nominatim_get('reverse',{'lat':lat,'lon':lon,'format':'jsonv2','addressdetails':1,'accept-language':'pt-BR','zoom':18})
    except Exception:
        return jsonify({'erro':'serviço de endereços indisponível'}),502
    a=d.get('address') or {}
    if not a: return jsonify({'erro':'nenhum endereço encontrado nessas coordenadas'}),404
    iso=a.get('ISO3166-2-lvl4','')
    return jsonify({
        'logradouro':a.get('road') or a.get('pedestrian') or a.get('path') or '',
        'numero':a.get('house_number',''),
        'bairro':a.get('suburb') or a.get('neighbourhood') or a.get('quarter') or a.get('city_district') or '',
        'cidade':a.get('city') or a.get('town') or a.get('village') or a.get('municipality') or '',
        'uf':iso.split('-')[-1] if iso.startswith('BR-') else '',
        'pais':a.get('country',''),
        'cep':a.get('postcode',''),
    })

@app.route('/import_keywords', methods=['POST'])
def import_keywords():
    f=request.files.get('file')
    if not f: return jsonify({'error':'sem arquivo'}),400
    ext=os.path.splitext(f.filename)[1].lower(); words=[]
    try:
        if ext=='.txt':
            words=[w.strip() for w in f.read().decode('utf-8',errors='ignore').replace('\n',',').split(',') if w.strip()]
        elif ext in('.xlsx','.xls'):
            import openpyxl
            wb=openpyxl.load_workbook(io.BytesIO(f.read()))
            for row in wb.active.iter_rows(values_only=True):
                for cell in row:
                    if cell: words.append(str(cell).strip())
        elif ext=='.xml':
            import xml.etree.ElementTree as ET
            for el in ET.parse(io.BytesIO(f.read())).iter():
                if el.text and el.text.strip(): words.append(el.text.strip())
    except Exception as e: return jsonify({'error':str(e)}),400
    return jsonify({'keywords':words})

@app.route('/models',methods=['GET'])
def get_models(): return jsonify(load_models())

@app.route('/models',methods=['POST'])
def save_model():
    d=request.get_json(silent=True) or {}; name=(d.get('name') or '').strip()
    if not name: return jsonify({'error':'nome obrigatório'}),400
    try:
        m=load_models(); m[name]=d.get('meta',{}); save_json(MODELS_FILE,m)
    except Exception as e:
        print(f"save_model error: {e}")
        return jsonify({'error':f'não foi possível gravar em {MODELS_FILE}: {e}'}),500
    return jsonify({'ok':True})

@app.route('/models/<name>',methods=['DELETE'])
def del_model(name):
    try:
        m=load_models(); m.pop(name,None); save_json(MODELS_FILE,m)
    except Exception as e:
        print(f"del_model error: {e}")
        return jsonify({'error':str(e)}),500
    return jsonify({'ok':True})

@app.route('/health')
def health(): return jsonify({'status':'ok','version':'6.0'})

if __name__=='__main__':
    port=int(os.environ.get('PORT',5000))
    app.run(debug=False,host='0.0.0.0',port=port)
