
"""Excel and PDF report generation."""
import html

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)

import analytics as an
from config import REPORT_DIR
from queries import get_engine, load_lines


def build_excel(target, tables):
    with pd.ExcelWriter(target, engine="openpyxl") as writer:
        for name, df in tables.items():
            sheet = name[:31]
            df.to_excel(writer, sheet_name=sheet, index=False)
            ws = writer.sheets[sheet]

            for idx, col in enumerate(df.columns, start=1):
                longest = max(
                    [len(str(col))]
                    + [len(str(v)) for v in df[col].head(200)]
                )
                letter = ws.cell(row=1, column=idx).column_letter
                ws.column_dimensions[letter].width = min(longest + 2, 40)


def _table(data):
    t = Table(data, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
    ]))
    return t


def build_pdf(target, title, kpi, monthly, recs):
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(target, pagesize=A4, title=title)

    rows = [["Month", "Revenue", "Profit", "MoM %"]]

    for r in monthly.tail(12).itertuples():
        mom = (
            "-" if pd.isna(r.mom_growth_pct)
            else f"{r.mom_growth_pct:.1f}"
        )
        rows.append([
            r.order_month,
            f"{r.revenue:,.0f}",
            f"{r.profit:,.0f}",
            mom
        ])

    story = [
        Paragraph(html.escape(title), styles["Title"]),
        Spacer(1, 12),
        Paragraph("Key Metrics", styles["Heading2"]),
        _table(
            [["Metric", "Value"]]
            + [[k, f"{v:,.2f}"] for k, v in kpi.items()]
        ),
        Spacer(1, 12),
        Paragraph("Last 12 Months", styles["Heading2"]),
        _table(rows),
        Spacer(1, 12),
        Paragraph("Business Recommendations", styles["Heading2"]),
    ]

    story += [
        Paragraph(f"- {html.escape(t)}", styles["BodyText"])
        for t in recs
    ]

    doc.build(story)


if __name__ == "__main__":
    lines = load_lines(get_engine())
    res = an.run_all(lines)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    tables = {
        "Monthly": res["monthly"],
        "Yearly": res["yearly"],
        "Category": res["cat"],
        "Product": res["prod"],
        "Region": res["reg"],
        "RFM": res["rfm"],
        "Forecast": res["fc"],
    }

    build_excel(
        str(REPORT_DIR / "ecommerce_report.xlsx"),
        tables
    )

    build_pdf(
        str(REPORT_DIR / "ecommerce_report.pdf"),
        "E-Commerce Business Report",
        res["kpi"],
        res["monthly"],
        res["recs"]
    )

    print(f"Reports saved in {REPORT_DIR}")
