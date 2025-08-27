#!/usr/bin/env python3
"""
番号ベースQRコード生成システム - ultra_simple_qr.pyの完全コピー版
QRデータだけを番号（1,2,3,4）に変更
"""

import qrcode
from qrcode.constants import ERROR_CORRECT_L
from PIL import Image, ImageDraw, ImageFont
import os

class NumberQRGenerator:
    def __init__(self):
        # ultra_simple_qr.pyと同じ製品情報
        self.products = {
            '1': {
                'code': 'BD-060',
                'name': '泰山普通石膏板',
                'quantity': 100,
                'row': 2
            },
            '2': {
                'code': 'US0503206MM2440', 
                'name': 'Stud 50mmx32mm',
                'quantity': 200,
                'row': 3
            },
            '3': {
                'code': 'AC-258',
                'name': 'KIRII Corner Bead',
                'quantity': 50,
                'row': 4
            },
            '4': {
                'code': 'AC-261',
                'name': '黃岩綿- 60g',
                'quantity': 10,
                'row': 5
            }
        }
        
        # 出力ディレクトリ
        self.output_dir = "qr_codes_number_only"
        os.makedirs(self.output_dir, exist_ok=True)
        
        print("🔢 番号ベースQRコード生成システム初期化完了")
        print(f"📁 出力ディレクトリ: {self.output_dir}")

    def generate_low_res_qr(self, product_id):
        """低解像度カメラ・遠距離対応QRコード生成（番号ベース）- ultra_simple_qr.pyの完全コピー"""
        
        if product_id not in self.products:
            return None
        
        product = self.products[product_id]
        product_code = product['code']
        
        # ultra_simple_qr.pyとの唯一の違い：QRデータを番号にする
        qr_data = product_id  # GoogleシートURLの代わりに番号
        
        # 超大マス設定（低解像度カメラ・遠距離対応）
        qr = qrcode.QRCode(
            version=1,  # 番号のみなので小さめ
            error_correction=qrcode.constants.ERROR_CORRECT_M,  # 中程度エラー訂正
            box_size=65,  # 超大マス（遠距離読み取り対応）
            border=1,    # 余白を極限まで削除
        )
        
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        # QRコード画像生成
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_img = qr_img.resize((1300, 1300))  # 1300px
        
        # QRコード + 製品名のみ
        canvas_width = 1500
        canvas_height = 1800
        canvas = Image.new('RGB', (canvas_width, canvas_height), 'white')
        
        # QRコードを中央に配置
        qr_x = (canvas_width - qr_img.width) // 2
        qr_y = (canvas_height - qr_img.height) // 2
        canvas.paste(qr_img, (qr_x, qr_y))
        
        # 製品名のみ描画
        draw = ImageDraw.Draw(canvas)
        
        try:
            font_medium = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 110)
        except:
            font_medium = ImageFont.load_default()
        
        # 製品名（黒色・中サイズ）
        product_name = product['name']
        text_x = 600  # X座標
        text_y = 1650  # Y座標
        draw.text((text_x, text_y), product_name, font=font_medium, fill='black', anchor='mm')
        
        # ファイル保存
        filename = f"{self.output_dir}/number_qr_{product_id}_{product_code}.png"
        canvas.save(filename, dpi=(300, 300))
        
        print(f"✅ 番号QRコード生成: {filename}")
        print(f"   QRデータ: '{qr_data}'")
        print(f"   製品名: {product['name']}")
        print(f"   マスサイズ: 65px (超大)")
        print(f"   画像サイズ: 1500x1800px")
        print(f"   QRコードサイズ: 1300x1300px")
        print(f"   余白: 1px")
        
        return filename

    def generate_all_low_res_qr(self):
        """全製品の低解像度対応QRコード生成"""
        print("🔲 番号ベース：低解像度カメラ・遠距離対応QRコード生成")
        print("=" * 80)
        
        qr_files = []
        for product_id in self.products.keys():
            filename = self.generate_low_res_qr(product_id)
            if filename:
                qr_files.append(filename)
                print()
        
        print("=" * 80)
        print(f"✅ 全{len(qr_files)}個の番号QRコード生成完了")
        
        return qr_files

def main():
    print("🔲 番号ベース：低解像度カメラ・遠距離対応QRコード生成システム")
    print("=" * 80)
    
    qr_gen = NumberQRGenerator()
    
    # 低解像度対応QRコード生成
    qr_files = qr_gen.generate_all_low_res_qr()
    
    print("\n🎯 完了！")
    print("📱 生成されたファイル:")
    for filename in qr_files:
        print(f"✅ {filename}")
    
    print(f"\n📋 次のステップ:")
    print("1. QRコードを37.5cm x 45cmで印刷（超大型）")
    print("2. 工場に設置")
    print("3. 携帯で番号読み取りテスト")
    print("4. Webアプリで番号入力テスト")

if __name__ == '__main__':
    main() k