import os, json, shutil, io, zipfile, uuid
from flask import Flask, render_template, request, jsonify, send_file, session
from werkzeug.utils import secure_filename
from PIL import Image
import piexif, requests as req
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'crazypro-rfa-2026')
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

UPLOAD_BASE = '/tmp/cp_uploads'
MODELS_FILE = '/tmp/cp_models.json'
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

def load_json(p):
    try: return json.load(open(p))
    except: return {}

def save_json(p, d):
    json.dump(d, open(p,'w'), ensure_ascii=False, indent=2)

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
    copyright=esc(meta.get('copyright','')); title=esc(meta.get('title') or meta.get('desc','')[:80])
    city=esc(meta.get('city','')); state=esc(meta.get('state',''))
    country=esc(meta.get('country','Brasil')); address=esc(meta.get('address',''))
    cep=esc(meta.get('cep','').replace('-','')); website=esc(meta.get('website',''))
    email=esc(meta.get('email','')); phone=esc(meta.get('phone') or meta.get('artist',''))
    category=esc(meta.get('mainCategory','')); rating=int(meta.get('rating') or 0)
    lat=meta.get('lat'); lon=meta.get('lon'); alt=meta.get('alt') or 0
    kw_raw=meta.get('keywords','')
    keywords=[esc(k.strip()) for k in kw_raw.split(',') if k.strip()] if kw_raw else []
    cat_raw=meta.get('categories','')
    subcats=[esc(c.strip()) for c in cat_raw.split(',') if c.strip()] if cat_raw else []
    kw_items='\n'.join(f'    <rdf:li>{k}</rdf:li>' for k in keywords)
    kw_block=f'  <dc:subject>\n   <rdf:Bag>\n{kw_items}\n   </rdf:Bag>\n  </dc:subject>' if keywords else ''
    sub_items='\n'.join(f'    <rdf:li>{c}</rdf:li>' for c in subcats)
    sub_block=f'  <photoshop:SupplementalCategories>\n   <rdf:Bag>\n{sub_items}\n   </rdf:Bag>\n  </photoshop:SupplementalCategories>' if subcats else ''
    gps_lat_xmp=gps_lon_xmp=gps_alt_xmp=''
    if lat and lon:
        try:
            flat=float(lat); flon=float(lon)
            flat_d=int(abs(flat)); flat_m=(abs(flat)-flat_d)*60
            flon_d=int(abs(flon)); flon_m=(abs(flon)-flon_d)*60
            lat_ref='S' if flat<0 else 'N'; lon_ref='W' if flon<0 else 'E'
            gps_lat_xmp=f'{flat_d},{flat_m:.6f}{lat_ref}'
            gps_lon_xmp=f'{flon_d},{flon_m:.6f}{lon_ref}'
            gps_alt_xmp=f'{int(float(alt))}/1'
        except: pass
    ms_rating=99 if rating==5 else(75 if rating==4 else(50 if rating==3 else(25 if rating==2 else(1 if rating==1 else 0))))
    country_code=country[:3].upper() if country else 'BRA'
    return f"""<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>
<x:xmpmeta xmlns:x='adobe:ns:meta/' x:xmptk='CrazyPro RFA 6.0'>
<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>
 <rdf:Description rdf:about='' xmlns:Iptc4xmpCore='http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/'>
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
 <rdf:Description rdf:about='' xmlns:MicrosoftPhoto='http://ns.microsoft.com/photo/1.0'>
  <MicrosoftPhoto:Rating>{ms_rating}</MicrosoftPhoto:Rating>
 </rdf:Description>
 <rdf:Description rdf:about='' xmlns:dc='http://purl.org/dc/elements/1.1/'>
  <dc:creator><rdf:Seq><rdf:li>{artist}</rdf:li></rdf:Seq></dc:creator>
  <dc:description><rdf:Alt><rdf:li xml:lang='x-default'>{desc}</rdf:li></rdf:Alt></dc:description>
  <dc:rights><rdf:Alt><rdf:li xml:lang='x-default'>{copyright}</rdf:li></rdf:Alt></dc:rights>
  <dc:title><rdf:Alt><rdf:li xml:lang='x-default'>{title}</rdf:li></rdf:Alt></dc:title>
{kw_block}
 </rdf:Description>
 <rdf:Description rdf:about='' xmlns:exif='http://ns.adobe.com/exif/1.0/'>
  <exif:GPSAltitude>{gps_alt_xmp}</exif:GPSAltitude>
  <exif:GPSAltitudeRef>0</exif:GPSAltitudeRef>
  <exif:GPSLatitude>{gps_lat_xmp}</exif:GPSLatitude>
  <exif:GPSLongitude>{gps_lon_xmp}</exif:GPSLongitude>
  <exif:GPSMapDatum>WGS-84</exif:GPSMapDatum>
  <exif:GPSVersionID>2.2.0.0</exif:GPSVersionID>
 </rdf:Description>
 <rdf:Description rdf:about='' xmlns:photoshop='http://ns.adobe.com/photoshop/1.0/'>
  <photoshop:City>{city}</photoshop:City>
  <photoshop:State>{state}</photoshop:State>
  <photoshop:Country>{country}</photoshop:Country>
  <photoshop:Credit>{artist}</photoshop:Credit>
  <photoshop:Source>{artist}</photoshop:Source>
  <photoshop:Headline>{title}</photoshop:Headline>
  <photoshop:Category>{category}</photoshop:Category>
  <photoshop:CaptionWriter>{artist}</photoshop:CaptionWriter>
  <photoshop:Instructions>{desc}</photoshop:Instructions>
{sub_block}
 </rdf:Description>
 <rdf:Description rdf:about='' xmlns:tiff='http://ns.adobe.com/tiff/1.0/'>
  <tiff:Artist>{artist}</tiff:Artist>
 </rdf:Description>
 <rdf:Description rdf:about='' xmlns:xmp='http://ns.adobe.com/xap/1.0/'>
  <xmp:Rating>{rating}</xmp:Rating>
  <xmp:BaseURL>{website}</xmp:BaseURL>
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

def write_exif(src, meta, out_path):
    try:
        img=Image.open(src)
        if img.mode not in('RGB','L'): img=img.convert('RGB')
        try:
            raw=img.info.get('exif',b'')
            exif=piexif.load(raw) if raw else {'0th':{},'Exif':{},'GPS':{},'1st':{}}
        except: exif={'0th':{},'Exif':{},'GPS':{},'1st':{}}
        z,gps=exif.get('0th',{}),exif.get('GPS',{})
        for val,tag in [(meta.get('desc'),piexif.ImageIFD.ImageDescription),
                        (meta.get('artist'),piexif.ImageIFD.Artist),
                        (meta.get('copyright'),piexif.ImageIFD.Copyright),
                        (meta.get('date'),piexif.ImageIFD.DateTime)]:
            if val: z[tag]=str(val).encode('utf-8','replace')
        lat=meta.get('lat'); lon=meta.get('lon'); alt=meta.get('alt')
        if lat and lon:
            lat,lon=float(lat),float(lon)
            gps[piexif.GPSIFD.GPSLatitudeRef]=b'N' if lat>=0 else b'S'
            gps[piexif.GPSIFD.GPSLatitude]=deg_to_dms(lat)
            gps[piexif.GPSIFD.GPSLongitudeRef]=b'E' if lon>=0 else b'W'
            gps[piexif.GPSIFD.GPSLongitude]=deg_to_dms(lon)
        if alt:
            av=float(alt)
            gps[piexif.GPSIFD.GPSAltitude]=(int(abs(av)*100),100)
            gps[piexif.GPSIFD.GPSAltitudeRef]=0 if av>=0 else 1
        exif['0th']=z; exif['GPS']=gps
        buf=io.BytesIO()
        img.save(buf,'JPEG',exif=piexif.dump(exif),quality=int(meta.get('quality',95)),optimize=False,subsampling=0)
        jpeg_bytes=inject_xmp_full(buf.getvalue(), meta)
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
    files=request.files.getlist('files'); saved=[]
    for f in files:
        ext=os.path.splitext(f.filename)[1].lower()
        if ext not in SUPPORTED: continue
        fname=secure_filename(f.filename)
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
        orig_base=os.path.splitext(fname)[0]
        global_i=index+i
        if rename:
            base=rename.replace('{n}',str(global_i+1).zfill(3)).replace('{name}',orig_base).replace('{date}',datetime.now().strftime('%Y%m%d'))
        else:
            base=orig_base
        out_name=base+'.jpg'
        out_path=os.path.join(out_dir,out_name)
        # Avoid overwrite
        counter=1
        while os.path.exists(out_path) and out_path!=os.path.join(out_dir,orig_base+'.jpg'):
            out_name=f"{base}_{counter}.jpg"; out_path=os.path.join(out_dir,out_name); counter+=1
        ok=write_exif(src,meta,out_path)
        results.append({'file':fname,'out':out_name,'ok':ok,'sid':sid})
    return jsonify({'results':results,'sid':sid})

@app.route('/download_all/<sid>')
def download_all(sid):
    out_dir=os.path.join(UPLOAD_BASE,sid,'output')
    if not os.path.exists(out_dir): return 'Nenhum arquivo',404
    files=[f for f in os.listdir(out_dir) if f.endswith('.jpg')]
    if not files: return 'Pasta vazia',404
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as zf:
        for f in files: zf.write(os.path.join(out_dir,f),f)
    buf.seek(0)
    return send_file(buf,as_attachment=True,download_name='crazypro_fotos.zip',mimetype='application/zip')

@app.route('/download_file/<sid>/<fn>')
def download_file(sid,fn):
    p=os.path.join(UPLOAD_BASE,sid,'output',fn)
    return send_file(p,as_attachment=True,download_name=fn) if os.path.exists(p) else ('não encontrado',404)

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
    cep=cep.replace('-','').replace('.','')
    try:
        r=req.get(f'https://viacep.com.br/ws/{cep}/json/',timeout=5)
        return jsonify(r.json())
    except: return jsonify({'erro':True}),400

@app.route('/geocode')
def geocode():
    q=request.args.get('q','')
    try:
        r=req.get(f'https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1',
            headers={'User-Agent':'CrazyPro-RFA/1.0'},timeout=8)
        return jsonify(r.json())
    except: return jsonify([]),400

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
def get_models(): return jsonify(load_json(MODELS_FILE))

@app.route('/models',methods=['POST'])
def save_model():
    d=request.json; name=d.get('name','').strip()
    if not name: return jsonify({'error':'nome obrigatório'}),400
    m=load_json(MODELS_FILE); m[name]=d.get('meta',{}); save_json(MODELS_FILE,m)
    return jsonify({'ok':True})

@app.route('/models/<name>',methods=['DELETE'])
def del_model(name):
    m=load_json(MODELS_FILE); m.pop(name,None); save_json(MODELS_FILE,m)
    return jsonify({'ok':True})

@app.route('/health')
def health(): return jsonify({'status':'ok','version':'6.0'})

if __name__=='__main__':
    port=int(os.environ.get('PORT',5000))
    app.run(debug=False,host='0.0.0.0',port=port)
