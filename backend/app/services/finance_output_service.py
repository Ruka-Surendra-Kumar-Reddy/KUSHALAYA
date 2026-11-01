"""Payroll & billing export artifacts — PDF payslips, invoice PDF, bank CSV."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.csv_safe import SafeWriter
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.invoice import Invoice, InvoiceLine
from app.models.payroll_run import PayrollLine, PayrollRun
from app.models.tenant import Tenant
from app.core.markets import market_meta, tenant_market


def _format_money(amount: float, tenant: Tenant | None) -> str:
    meta = market_meta(tenant_market(tenant) if tenant else None)
    symbol = meta["currency_symbol"]
    return f"{symbol}{amount:,.2f}"


def _display_name(first: str | None, last: str | None) -> str:
    name = f"{first or ''} {last or ''}".strip()
    return name or "Unknown"


class FinanceOutputService:

    @staticmethod
    def aggregate_payroll(
        lines: list[PayrollLine],
        caregivers: dict[int, Caregiver],
    ) -> list[dict]:
        buckets: dict[int, dict] = {}
        for line in lines:
            cg_id = line.caregiver_id
            if cg_id not in buckets:
                cg = caregivers.get(cg_id)
                buckets[cg_id] = {
                    "caregiver_id": cg_id,
                    "caregiver_name": _display_name(
                        cg.first_name if cg else None,
                        cg.last_name if cg else None,
                    ),
                    "hours": 0.0,
                    "gross": 0.0,
                    "visits": [],
                }
            buckets[cg_id]["hours"] += line.hours
            buckets[cg_id]["gross"] += line.amount
            buckets[cg_id]["visits"].append(
                {
                    "description": line.description or "",
                    "hours": line.hours,
                    "rate": line.hourly_rate,
                    "amount": line.amount,
                }
            )
        rows = list(buckets.values())
        for row in rows:
            row["hours"] = round(row["hours"], 2)
            row["gross"] = round(row["gross"], 2)
        rows.sort(key=lambda r: r["caregiver_name"])
        return rows

    @classmethod
    def payslip_pdf(
        cls,
        *,
        tenant: Tenant,
        run: PayrollRun,
        caregiver_row: dict,
    ) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm)
        styles = getSampleStyleSheet()
        story: list = []

        story.append(Paragraph(tenant.name, styles["Title"]))
        story.append(Paragraph("Caregiver Payslip", styles["Heading2"]))
        story.append(Spacer(1, 0.3 * cm))
        story.append(
            Paragraph(
                f"Period: {run.period_start} to {run.period_end}",
                styles["Normal"],
            )
        )
        story.append(
            Paragraph(
                f"Payroll run #{run.id} · Status: {run.status}",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 0.4 * cm))
        story.append(
            Paragraph(
                f"<b>Caregiver:</b> {caregiver_row['caregiver_name']} "
                f"(#{caregiver_row['caregiver_id']})",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 0.5 * cm))

        table_data = [["Description", "Hours", "Rate", "Amount"]]
        for visit in caregiver_row["visits"]:
            table_data.append(
                [
                    visit["description"],
                    f"{visit['hours']:.2f}",
                    _format_money(visit["rate"], tenant),
                    _format_money(visit["amount"], tenant),
                ]
            )
        table_data.append(
            [
                "Total",
                f"{caregiver_row['hours']:.2f}",
                "",
                _format_money(caregiver_row["gross"], tenant),
            ]
        )

        table = Table(table_data, colWidths=[8 * cm, 2.5 * cm, 3 * cm, 3 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0f4f8")),
                ]
            )
        )
        story.append(table)

        deductions = caregiver_row.get("deductions") or []
        total_deductions = caregiver_row.get("total_deductions", 0.0)
        if deductions:
            story.append(Spacer(1, 0.4 * cm))
            story.append(Paragraph("Statutory deductions", styles["Heading4"]))
            ded_data = [["Type", "Amount"]]
            for d in deductions:
                ded_data.append([d["deduction_type"], _format_money(d["amount"], tenant)])
            ded_data.append(["Total deductions", _format_money(total_deductions, tenant)])
            ded_table = Table(ded_data, colWidths=[10 * cm, 4 * cm])
            ded_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ]
                )
            )
            story.append(ded_table)

        net = caregiver_row.get("net", caregiver_row["gross"])
        story.append(Spacer(1, 0.5 * cm))
        story.append(
            Paragraph(
                f"<b>Gross pay:</b> {_format_money(caregiver_row['gross'], tenant)}",
                styles["Normal"],
            )
        )
        if total_deductions:
            story.append(
                Paragraph(
                    f"<b>Total deductions:</b> {_format_money(total_deductions, tenant)}",
                    styles["Normal"],
                )
            )
        story.append(
            Paragraph(
                f"<b>Net pay:</b> {_format_money(net, tenant)}",
                styles["Heading3"],
            )
        )
        if run.finalized_at:
            story.append(
                Paragraph(
                    f"Finalized: {run.finalized_at.date()}",
                    styles["Normal"],
                )
            )

        doc.build(story)
        return buffer.getvalue()

    @classmethod
    def payroll_run_pdf(
        cls,
        *,
        tenant: Tenant,
        run: PayrollRun,
        aggregated: list[dict],
    ) -> bytes:
        """Single PDF with one payslip section per caregiver."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm)
        styles = getSampleStyleSheet()
        story: list = []

        story.append(Paragraph(tenant.name, styles["Title"]))
        story.append(Paragraph(f"Payroll Run #{run.id}", styles["Heading2"]))
        total_net = run.total_net if run.total_net else run.total_amount
        story.append(
            Paragraph(
                f"{run.period_start} – {run.period_end} · "
                f"Gross {_format_money(run.total_amount, tenant)} · "
                f"Deductions {_format_money(run.total_deductions or 0, tenant)} · "
                f"Net {_format_money(total_net, tenant)}",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 0.5 * cm))

        summary_data = [["Caregiver", "Hours", "Gross", "Deductions", "Net pay"]]
        for row in aggregated:
            summary_data.append(
                [
                    row["caregiver_name"],
                    f"{row['hours']:.2f}",
                    _format_money(row["gross"], tenant),
                    _format_money(row.get("total_deductions", 0), tenant),
                    _format_money(row.get("net", row["gross"]), tenant),
                ]
            )
        summary_data.append(
            [
                "Total",
                "",
                _format_money(run.total_amount, tenant),
                _format_money(run.total_deductions or 0, tenant),
                _format_money(total_net, tenant),
            ]
        )
        table = Table(summary_data, colWidths=[5 * cm, 2 * cm, 3 * cm, 3 * cm, 3 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ]
            )
        )
        story.append(table)
        doc.build(story)
        return buffer.getvalue()

    @classmethod
    def bank_transfer_csv(
        cls,
        *,
        tenant: Tenant,
        run: PayrollRun,
        aggregated: list[dict],
        caregivers: dict[int, Caregiver],
    ) -> str:
        currency = market_meta(tenant_market(tenant))["currency"]
        output = io.StringIO()
        writer = SafeWriter(output)
        writer.writerow(
            [
                "Beneficiary Name",
                "Account Number",
                "IFSC",
                f"Net Amount ({currency})",
                "Narration",
                "Caregiver ID",
            ]
        )
        for row in aggregated:
            cg = caregivers.get(row["caregiver_id"])
            bank = {}
            if cg and cg.custom_attributes:
                bank = cg.custom_attributes.get("bank") or {}
            beneficiary = (
                bank.get("beneficiary_name")
                or row["caregiver_name"]
            )
            writer.writerow(
                [
                    beneficiary,
                    bank.get("account_number", ""),
                    bank.get("ifsc", ""),
                    f"{row.get('net', row['gross']):.2f}",
                    f"PAYROLL-{run.id}-CG{row['caregiver_id']}",
                    row["caregiver_id"],
                ]
            )
        return output.getvalue()

    @classmethod
    def invoice_pdf(
        cls,
        *,
        tenant: Tenant,
        invoice: Invoice,
        elder: Elder,
        lines: list[InvoiceLine],
    ) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm)
        styles = getSampleStyleSheet()
        story: list = []

        inv_no = invoice.invoice_number or f"INV-{invoice.id}"
        story.append(Paragraph(tenant.name, styles["Title"]))
        story.append(Paragraph("Tax Invoice", styles["Heading2"]))
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph(f"<b>Invoice:</b> {inv_no}", styles["Normal"]))
        story.append(
            Paragraph(
                f"<b>Bill to:</b> {_display_name(elder.first_name, elder.last_name)}",
                styles["Normal"],
            )
        )
        if elder.address:
            story.append(Paragraph(elder.address, styles["Normal"]))
        story.append(
            Paragraph(
                f"Service period: {invoice.period_start} – {invoice.period_end}",
                styles["Normal"],
            )
        )
        if invoice.issued_at:
            story.append(
                Paragraph(
                    f"Issued: {invoice.issued_at.date()}",
                    styles["Normal"],
                )
            )
        if invoice.due_date:
            story.append(
                Paragraph(f"<b>Due date:</b> {invoice.due_date}", styles["Normal"])
            )
        story.append(Spacer(1, 0.4 * cm))

        table_data = [["Description", "Hours", "Rate", "Amount"]]
        for line in lines:
            table_data.append(
                [
                    line.description,
                    f"{line.hours:.2f}",
                    _format_money(line.unit_price, tenant),
                    _format_money(line.amount, tenant),
                ]
            )

        subtotal = invoice.subtotal or sum(ln.amount for ln in lines)
        table_data.append(["Subtotal", "", "", _format_money(subtotal, tenant)])
        if invoice.tax_amount:
            table_data.append(
                [
                    f"GST ({invoice.tax_rate:.0f}%)",
                    "",
                    "",
                    _format_money(invoice.tax_amount, tenant),
                ]
            )
        table_data.append(
            ["Total due", "", "", _format_money(invoice.total_amount, tenant)]
        )
        if invoice.amount_paid:
            table_data.append(
                ["Amount paid", "", "", _format_money(invoice.amount_paid, tenant)]
            )
            balance = max(0.0, invoice.total_amount - invoice.amount_paid)
            table_data.append(["Balance", "", "", _format_money(balance, tenant)])

        table = Table(table_data, colWidths=[8 * cm, 2.5 * cm, 3 * cm, 3 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTNAME", (0, -2), (-1, -1), "Helvetica-Bold"),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 0.4 * cm))
        story.append(
            Paragraph(
                f"{tenant.address}, {tenant.city}, {tenant.state}",
                styles["Normal"],
            )
        )
        doc.build(story)
        return buffer.getvalue()

    @staticmethod
    def aging_bucket(due: date | None, today: date) -> str:
        if due is None:
            return "current"
        days = (today - due).days
        if days <= 0:
            return "current"
        if days <= 30:
            return "days_1_30"
        if days <= 60:
            return "days_31_60"
        if days <= 90:
            return "days_61_90"
        return "over_90"
