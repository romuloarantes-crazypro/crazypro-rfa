# ExifBoost Pro

Ferramenta da **RFA Marketing Digital** para gravar metadados (EXIF, IPTC e XMP) em fotos e preparar os arquivos para o Perfil da Empresa no Google (Google Meu Negócio).

## O que faz

- Importa várias fotos de uma vez (JPG, PNG, TIFF) e mostra uma galeria com mapa.
- Grava descrição, autor, copyright, palavras-chave, categorias, avaliação, redes sociais e contatos nos metadados.
- Localização: preenche o endereço pelo CEP, por coordenadas ou clicando no mapa, e grava o GPS.
- Preserva a data original de captura de cada foto. A data do formulário só é usada em fotos sem data, ou quando você pedir para substituir.
- Gera os arquivos em JPG nos formatos 1080×1080, 1200×900, 1080×608 ou no tamanho original, e avisa se algum passar de 5 MB (limite do Google).
- Salva modelos de preenchimento para reutilizar.
- Baixa as fotos processadas individualmente ou em ZIP.

> Metadados ajudam a organizar e dar contexto às fotos, mas **não garantem posição nas buscas**, e o Google pode removê-los ou ignorá-los. Grave apenas dados verdadeiros (data, local e autoria) e use fotos suas ou licenciadas.

## Instalar no Mac

1. Instale o Python 3 em python.org (se ainda não tiver).
2. Baixe o ZIP do projeto: `https://github.com/romuloarantes-crazypro/crazypro-rfa/archive/refs/heads/main.zip` e extraia a pasta onde quiser.
3. Na primeira vez, o macOS bloqueia arquivos baixados da internet: clique com o botão direito em `INICIAR_MAC.command`, escolha **Abrir** e confirme **Abrir** de novo. Nas vezes seguintes basta dar duplo clique.
   - Se aparecer "permissão negada", abra o Terminal na pasta e rode `chmod +x INICIAR_MAC.command ATUALIZAR_MAC.command`.
4. Na primeira execução ele prepara um ambiente próprio e instala as dependências (cerca de 1 minuto, precisa de internet). O app abre em `http://127.0.0.1:8080`.
5. Para atualizar: baixe o ZIP novo e substitua a pasta. Se você instalou com `git clone`, use `ATUALIZAR_MAC.command`. Seus modelos salvos ficam fora da pasta do projeto e não se perdem.

O app abre só no seu computador. Para liberar para outros aparelhos da rede local, defina `EXIFBOOST_HOST=0.0.0.0` antes de iniciar (use apenas em rede de confiança).

## Instalar no Windows

1. Instale o Python em python.org, marcando **Add Python to PATH**.
2. Baixe o ZIP do projeto: `https://github.com/romuloarantes-crazypro/crazypro-rfa/archive/refs/heads/main.zip` e extraia.
3. Dê duplo clique em `INSTALAR_WINDOWS.bat`. Ele instala em `D:\CrazyPro-RFA` (ou `C:\CrazyPro-RFA`, se não houver disco D) e cria o atalho **ExifBoost Pro** na Área de Trabalho.
4. Para atualizar, baixe o ZIP de novo e rode o instalador outra vez.

## Rodar manualmente

```
pip install -r requirements.txt
PORT=8080 python3 app.py
```

Abra `http://localhost:8080`. Por padrão o app só aceita conexões do próprio computador.

## Versão online (opcional)

O app pode rodar em um servidor, com acesso por **código de equipe**. Cada código abre um espaço separado, com os próprios modelos salvos. Variáveis de ambiente:

| Variável | Para que serve |
|---|---|
| `EXIFBOOST_ENV=production` | Ativa o modo online. Exige as duas variáveis abaixo, senão o app não inicia. |
| `SECRET_KEY` | Texto aleatório com pelo menos 16 caracteres. |
| `EXIFBOOST_ACCESS_CODES` | `equipe=codigo,outra=codigo2` (códigos com pelo menos 8 caracteres). |
| `EXIFBOOST_DATA_DIR` | Pasta persistente dos modelos (ex.: um volume em `/data`). |
| `EXIFBOOST_MAX_UPLOAD_MB` | Limite de envio por requisição (padrão 200). |
| `EXIFBOOST_RETENTION_HOURS` | Horas até apagar fotos temporárias (padrão 24). |
| `EXIFBOOST_CONTACT` | Contato incluído na identificação enviada ao serviço de endereços (OpenStreetMap). |

O `Procfile` e o `railway.json` já estão prontos para publicar no Railway (`gunicorn`, um processo com 4 threads, verificação de saúde em `/health`).

## Privacidade

- As fotos importadas e geradas ficam numa pasta temporária do servidor e são apagadas ao usar "Limpar" ou após 24 horas sem uso.
- Modelos salvos ficam em arquivo (pasta do usuário no modo local, `EXIFBOOST_DATA_DIR` no modo online).
- Endereços e coordenadas são consultados no OpenStreetMap (Nominatim) e CEPs no ViaCEP, BrasilAPI e OpenCEP.

## Direitos

© RFA Marketing Digital — CNPJ 64.810.923/0001-91. Todos os direitos reservados.
