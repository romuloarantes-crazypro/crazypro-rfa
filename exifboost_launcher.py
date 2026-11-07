"""Ponto de entrada do ExifBoost Pro empacotado (.exe): abre o app e o navegador."""
import os, socket, sys, threading, webbrowser


def porta_livre(preferida):
    for porta in (preferida, 0):
        s = socket.socket()
        try:
            s.bind(('127.0.0.1', porta))
            return s.getsockname()[1]
        except OSError:
            pass
        finally:
            s.close()
    return preferida


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    import app as exifboost
    porta = porta_livre(int(os.environ.get('PORT', '8080')))
    url = f'http://127.0.0.1:{porta}'
    print('ExifBoost Pro - RFA Marketing Digital')
    print(f'Abrindo {url}')
    print('Para encerrar o app, feche esta janela.')
    if not os.environ.get('EXIFBOOST_NO_BROWSER'):
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    exifboost.app.run(host='127.0.0.1', port=porta, debug=False, use_reloader=False, threaded=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as erro:
        print(f'\nNão foi possível iniciar o ExifBoost Pro: {erro}')
        input('Pressione Enter para fechar...')
