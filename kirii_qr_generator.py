#!/usr/bin/env python3
"""
KIRII在庫管理QRコード生成システム
携帯カメラ＆CCTV対応の大型QRコード生成
"""

import qrcode
from PIL import Image, ImageDraw, ImageFont
import os
import json
from datetime import datetime

class KiriiQRGenerator:
    def __init__(self):
        # スプレッドシートデータ（実際のデータ）
        self.inventory_data = {
            "BD-060": {
                "name": "泰山普通石膏板 4'x6'x12mmx 4.5mm",
                "quantity": 100,
                "updated": "2025-07-26"
            },
            "US0503206MM2440": {
                "name": "Stud 50mmx32mmx0.6mmx2440mm",
                "quantity": 200,
                "updated": "2025-07-26"
            },
            "AC-258": {
                "name": "KIRII Corner Bead 2440mm (25pcs/bdl)(0.4mm 鋁)",
                "quantity": 50,
                "updated": "2025-07-26"
            },
            "AC-261": {
                "name": "黃岩綿- 60g (6pcs/pack)",
                "quantity": 10,
                "updated": "2025-07-26"
            }
        }
        
        # Vercelプラットフォームの基本URL（後で設定）
        self.base_url = "https://kirii-inventory.vercel.app"
        
        # QRコード出力ディレクトリ
        self.output_dir = "qr_codes"
        os.makedirs(self.output_dir, exist_ok=True)
        
        print("🏭 KIRII QRコード生成システム初期化完了")
        print(f"📁 出力ディレクトリ: {self.output_dir}")
        print(f"🌐 ベースURL: {self.base_url}")

    def generate_qr_code(self, product_code, size='large'):
        """
        QRコード生成（CCTV対応の大型サイズ）
        """
        # QRコードに埋め込むURL
        qr_url = f"{self.base_url}/product/{product_code}"
        
        # QRコード設定
        if size == 'large':
            # CCTV用：大型、高エラー訂正
            qr = qrcode.QRCode(
                version=3,  # サイズ
                error_correction=qrcode.constants.ERROR_CORRECT_H,  # 高エラー訂正
                box_size=20,  # 各マスのピクセル数
                border=10,   # 境界の幅
            )
        else:
            # 携帯用：標準サイズ
            qr = qrcode.QRCode(
                version=2,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
            )
        
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # QRコード画像生成
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        return qr_img, qr_url

    def create_labeled_qr(self, product_code):
        """
        製品情報付きQRコード作成
        """
        if product_code not in self.inventory_data:
            print(f"❌ 製品コード {product_code} が見つかりません")
            return None
        
        product_info = self.inventory_data[product_code]
        
        # QRコード生成
        qr_img, qr_url = self.generate_qr_code(product_code, 'large')
        
        # 画像サイズを取得
        qr_width, qr_height = qr_img.size
        
        # ラベル付き画像の作成（QRコード + テキスト情報）
        label_height = 200
        total_width = max(qr_width, 800)
        total_height = qr_height + label_height
        
        # 新しい画像を作成
        labeled_img = Image.new('RGB', (total_width, total_height), 'white')
        
        # QRコードを中央に配置
        qr_x = (total_width - qr_width) // 2
        labeled_img.paste(qr_img, (qr_x, 0))
        
        # テキスト情報を追加
        draw = ImageDraw.Draw(labeled_img)
        
        try:
            # フォント設定（システムフォントを使用）
            title_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24)
            info_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 18)
            code_font = ImageFont.truetype("/System/Library/Fonts/Courier.ttf", 20)
        except:
            # フォントが見つからない場合はデフォルトフォント
            title_font = ImageFont.load_default()
            info_font = ImageFont.load_default()
            code_font = ImageFont.load_default()
        
        # テキスト描画位置
        text_y = qr_height + 20
        
        # 製品コード
        draw.text((50, text_y), f"製品コード: {product_code}", 
                 fill='black', font=code_font)
        
        # 製品名
        draw.text((50, text_y + 35), f"品名: {product_info['name']}", 
                 fill='black', font=info_font)
        
        # 在庫数量
        draw.text((50, text_y + 70), f"在庫数量: {product_info['quantity']}個", 
                 fill='red', font=title_font)
        
        # 更新日
        draw.text((50, text_y + 105), f"更新日: {product_info['updated']}", 
                 fill='gray', font=info_font)
        
        # URL
        draw.text((50, text_y + 140), f"URL: {qr_url}", 
                 fill='blue', font=info_font)
        
        return labeled_img

    def generate_all_qr_codes(self):
        """
        全製品のQRコード生成
        """
        print("=" * 60)
        print("🏭 KIRII在庫管理QRコード一括生成開始")
        print("=" * 60)
        
        generated_codes = []
        
        for product_code in self.inventory_data.keys():
            print(f"📱 生成中: {product_code}")
            
            # ラベル付きQRコード生成
            labeled_qr = self.create_labeled_qr(product_code)
            
            if labeled_qr:
                # ファイル保存
                filename = f"{self.output_dir}/KIRII_{product_code}_QR.png"
                labeled_qr.save(filename, 'PNG', quality=95, dpi=(300, 300))
                
                print(f"✅ 保存完了: {filename}")
                generated_codes.append({
                    'code': product_code,
                    'filename': filename,
                    'url': f"{self.base_url}/product/{product_code}",
                    'product_info': self.inventory_data[product_code]
                })
            else:
                print(f"❌ 生成失敗: {product_code}")
        
        # 生成情報をJSONで保存
        info_file = f"{self.output_dir}/qr_generation_info.json"
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump({
                'generated_at': datetime.now().isoformat(),
                'base_url': self.base_url,
                'codes': generated_codes
            }, f, ensure_ascii=False, indent=2)
        
        print("=" * 60)
        print(f"🎉 QRコード生成完了: {len(generated_codes)}個")
        print(f"📁 保存場所: {self.output_dir}/")
        print(f"📄 生成情報: {info_file}")
        print("=" * 60)
        
        return generated_codes

    def print_usage_guide(self):
        """
        使用方法ガイド
        """
        print("\n📋 QRコード使用ガイド")
        print("=" * 40)
        print("🎯 CCTV監視用:")
        print("  - 大型QRコード（高エラー訂正）")
        print("  - 低解像度カメラでも読み取り可能")
        print("  - 推奨印刷サイズ: A4用紙")
        print()
        print("📱 携帯カメラ用:")
        print("  - QRコードをスキャン")
        print("  - 自動でVercelプラットフォームに移動")
        print("  - 在庫情報を瞬時に表示")
        print()
        print("🌐 Vercelプラットフォーム:")
        print(f"  - ベースURL: {self.base_url}")
        print("  - 製品別URL: /product/[製品コード]")
        print("  - リアルタイム在庫確認")

def main():
    print("🏭 KIRII在庫管理QRコード生成システム")
    print("=" * 60)
    
    try:
        generator = KiriiQRGenerator()
        
        # 全QRコード生成
        generated_codes = generator.generate_all_qr_codes()
        
        # 使用方法ガイド表示
        generator.print_usage_guide()
        
        print(f"\n✅ 生成完了: {len(generated_codes)}個のQRコード")
        print("📱 次のステップ: Vercelプラットフォームの作成")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        print(f"詳細: {traceback.format_exc()}")

if __name__ == '__main__':
    main() 