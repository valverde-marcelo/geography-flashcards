import os
import subprocess
from PIL import Image

# Configurações do Cartão de Crédito (ISO/IEC 7810 ID-1)
# Tamanho: 85.60 x 53.98 mm
# Para alta resolução (ex: 300 DPI), calculamos os pixels:
# (85.6 / 25.4) * 300 = 1011 px
# (53.98 / 25.4) * 300 = 638 px
# Vamos usar 600 DPI para garantir uma "boa resolução" conforme pedido.
DPI = 600
WIDTH = int((85.60 / 25.4) * DPI)
HEIGHT = int((53.98 / 25.4) * DPI)

INPUT_DIR = "/home/ubuntu/flags_project/raw_svg"
OUTPUT_DIR = "/home/ubuntu/flags_project/credit_card_flags"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def convert_svg_to_png(svg_path, png_path, width, height):
    # Usando rsvg-convert (parte do librsvg2-bin) para converter SVG para PNG mantendo a qualidade
    # O comando tenta preencher o tamanho mantendo o aspect ratio ou forçando se necessário.
    # Para cartões, o ideal é centralizar a bandeira ou preencher.
    try:
        # Primeiro, convertemos para um PNG temporário com a largura desejada
        temp_png = png_path + ".temp.png"
        subprocess.run([
            "rsvg-convert",
            "-w", str(width),
            "-h", str(height),
            "--keep-aspect-ratio",
            "-f", "png",
            "-o", temp_png,
            svg_path
        ], check=True)
        
        # Agora usamos PIL para colocar a bandeira em um canvas do tamanho exato do cartão (fundo branco ou transparente)
        img = Image.open(temp_png)
        canvas = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        
        # Calcular posição para centralizar
        img_w, img_h = img.size
        offset = ((width - img_w) // 2, (height - img_h) // 2)
        canvas.paste(img, offset)
        
        # Salvar final
        canvas.save(png_path, "PNG")
        os.remove(temp_png)
        return True
    except Exception as e:
        print(f"Erro ao processar {svg_path}: {e}")
        return False

files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".svg")]
print(f"Iniciando conversão de {len(files)} bandeiras...")

count = 0
for filename in files:
    svg_path = os.path.join(INPUT_DIR, filename)
    png_path = os.path.join(OUTPUT_DIR, filename.replace(".svg", ".png"))
    if convert_svg_to_png(svg_path, png_path, WIDTH, HEIGHT):
        count += 1

print(f"Concluído! {count} bandeiras processadas em {WIDTH}x{HEIGHT} px ({DPI} DPI).")
