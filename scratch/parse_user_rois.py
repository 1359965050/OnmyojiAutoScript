import csv
import sys

def parse_csv(path):
    xs = []
    ys = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if not row:
                continue
            xs.append(int(row[0]))
            ys.append(int(row[1]))
    if not xs:
        return None
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    return (x_min, y_min, x_max - x_min + 1, y_max - y_min + 1)

roi1 = parse_csv(r"f:\daima\OAS\docs\确认按钮ROI.csv")
roi2 = parse_csv(r"f:\daima\OAS\docs\返回按钮ROI.csv")

print(f"确认按钮ROI: {roi1} center: ({roi1[0] + roi1[2]//2}, {roi1[1] + roi1[3]//2})")
print(f"返回按钮ROI: {roi2} center: ({roi2[0] + roi2[2]//2}, {roi2[1] + roi2[3]//2})")
