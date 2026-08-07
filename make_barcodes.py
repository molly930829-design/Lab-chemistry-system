import barcode
from barcode.writer import ImageWriter

print("開始生成 1,000 張條碼，請稍候...")

# 將範圍改為 1 到 1000 ( range(1, 1001) )
for i in range(1, 1001):
    code_text = f"CHEM-{i:05d}"
    code128 = barcode.get("code128", code_text, writer=ImageWriter())
    # 存成圖片檔
    code128.save(f"barcode_{code_text}")

print("🎉 成功！1,000 張條碼圖片已全部產出完成！")
