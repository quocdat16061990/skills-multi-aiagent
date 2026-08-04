"""Render a self-contained Gmail-compatible HTML summary from current analysis data."""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path


def format_number(value) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(value):,}".replace(",", ".")


def top_rows(rows: list[dict], limit: int = 5) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: row.get("views") if isinstance(row.get("views"), (int, float)) else -1,
        reverse=True,
    )[:limit]


def share_of_views(rows: list[dict], limit: int) -> float:
    views = sorted(
        [row["views"] for row in rows if isinstance(row.get("views"), (int, float))],
        reverse=True,
    )
    total = sum(views)
    return round(sum(views[:limit]) / total * 100, 1) if total else 0.0


def counter_for(rows: list[dict], field: str) -> Counter:
    return Counter(value for row in rows for value in row.get(field, []))


def counter_html(counter: Counter, limit: int = 5) -> str:
    items = counter.most_common(limit)
    if not items:
        return "Chưa có dữ liệu"
    return "<br>".join(f"{escape(str(label))}: {count}" for label, count in items)


def replace_template(template: str, values: dict[str, str]) -> str:
    placeholders = set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", template))
    missing = sorted(placeholders - values.keys())
    if missing:
        raise ValueError(f"Thiếu dữ liệu template: {', '.join(missing)}")
    rendered = template
    for key in placeholders:
        rendered = rendered.replace("{{" + key + "}}", values[key])
    if re.search(r"\{\{[^}]+\}\}", rendered):
        raise ValueError("HTML còn placeholder sau render")
    return rendered


def build_email_content(
    template_path: Path,
    output_path: Path,
    channel: dict,
    rows: list[dict],
    stats: dict,
    collected: dict,
    workbook_path: Path,
    generated_at: datetime,
) -> tuple[Path, str]:
    template = template_path.read_text(encoding="utf-8")
    all_stats = stats.get("all", {})
    topic_counter = counter_for(rows, "topics")
    hook_counter = counter_for(rows, "hooks")
    meaningful_topics = Counter(
        {label: count for label, count in topic_counter.items() if label != "Khác/Chưa mã hóa"}
    )
    topic_source = meaningful_topics or topic_counter
    top_topics = topic_source.most_common(3)
    top_hooks = hook_counter.most_common(3)
    top_videos = top_rows(rows)

    channel_title = str(channel.get("title") or "Kênh YouTube")
    report_date = generated_at.strftime("%d/%m/%Y")
    source = str(collected.get("source") or "N/A")
    mean_views = all_stats.get("mean")
    median_views = all_stats.get("median")
    top_one_share = share_of_views(rows, 1)
    top_ten_share = share_of_views(rows, 10)
    topic_summary = ", ".join(f"{label} ({count})" for label, count in top_topics) or "chưa đủ dữ liệu"
    hook_summary = ", ".join(f"{label} ({count})" for label, count in top_hooks) or "chưa đủ dữ liệu"

    summary_items = [
        f"<li><strong>Chủ đề nổi bật:</strong> {escape(topic_summary)}. Các nhãn có thể chồng lấp.</li>",
        (
            "<li><strong>Phân phối lượt xem:</strong> "
            f"trung bình {format_number(mean_views)}, median {format_number(median_views)}; "
            f"video đứng đầu chiếm {str(top_one_share).replace('.', ',')}% và top 10 chiếm "
            f"{str(top_ten_share).replace('.', ',')}% tổng views.</li>"
        ),
        f"<li><strong>Hook xuất hiện nhiều:</strong> {escape(hook_summary)}.</li>",
    ]
    if top_videos:
        summary_items.append(
            "<li><strong>Video dẫn đầu:</strong> "
            f"{escape(str(top_videos[0].get('title') or 'N/A'))} — "
            f"{format_number(top_videos[0].get('views'))} views.</li>"
        )

    table_rows = []
    for index, row in enumerate(top_videos, 1):
        table_rows.append(
            "<tr>"
            f'<td style="padding:9px;border:1px solid #e2e8ef;">{index}</td>'
            f'<td style="padding:9px;border:1px solid #e2e8ef;">{escape(str(row.get("title") or "N/A"))}</td>'
            f'<td align="right" style="padding:9px;border:1px solid #e2e8ef;font-weight:700;">{format_number(row.get("views"))}</td>'
            "</tr>"
        )
    if not table_rows:
        table_rows.append(
            '<tr><td colspan="3" style="padding:9px;border:1px solid #e2e8ef;">Không có video hợp lệ.</td></tr>'
        )

    recommendations = []
    if top_topics:
        recommendations.append(
            "<li><strong>Kiểm thử chủ đề dẫn đầu:</strong> "
            f"ưu tiên các biến thể của {escape(top_topics[0][0])}, nhưng không xem tần suất là bằng chứng nhân quả.</li>"
        )
    if top_hooks:
        recommendations.append(
            "<li><strong>Kiểm thử hook nổi bật:</strong> "
            f"thử {escape(top_hooks[0][0])} với cùng chủ đề và định dạng để so sánh công bằng.</li>"
        )
    if isinstance(mean_views, (int, float)) and isinstance(median_views, (int, float)) and mean_views > median_views * 1.5:
        recommendations.append(
            "<li><strong>Dùng median khi đánh giá:</strong> phân phối bị kéo lệch bởi một số video đột biến; không chỉ nhìn average.</li>"
        )
    recommendations.append(
        "<li><strong>Tách fact, coding và inference:</strong> dùng workbook để kiểm tra bằng chứng trước khi áp dụng chiến thuật.</li>"
    )

    limitations = [
        "Chỉ dùng dữ liệu công khai, không đăng nhập và không vượt cơ chế chặn.",
        "Chủ đề/hook là nhãn deterministic theo cấu hình, không phải tuyên bố của tác giả.",
        "Views/ngày chỉ có ý nghĩa khi nguồn cung cấp ngày đăng tuyệt đối chắc chắn.",
    ]
    limitations.extend(str(warning) for warning in collected.get("warnings", []))

    values = {
        "EMAIL_PREHEADER": escape(f"Báo cáo phân tích kênh {channel_title}"),
        "REPORT_KICKER": "YouTube Competitor Analysis",
        "REPORT_TITLE": escape(channel_title),
        "REPORT_SUBTITLE": escape(
            f"Khảo sát {len(rows)} video công khai · Ngày {report_date} · Nguồn {source}"
        ),
        "METRIC_1_VALUE": format_number(len(rows)),
        "METRIC_1_LABEL": "Video",
        "METRIC_2_VALUE": format_number(all_stats.get("total")),
        "METRIC_2_LABEL": "Tổng views",
        "METRIC_3_VALUE": format_number(median_views),
        "METRIC_3_LABEL": "Median views",
        "METRIC_4_VALUE": format_number(all_stats.get("max")),
        "METRIC_4_LABEL": "Cao nhất",
        "SUMMARY_HEADING": "Kết luận nhanh",
        "SUMMARY_ITEMS_HTML": "".join(summary_items),
        "TOP_TABLE_HEADING": "Top nội dung quan sát được",
        "TOP_TABLE_TITLE_LABEL": "Tiêu đề",
        "TOP_TABLE_VALUE_LABEL": "Views",
        "TOP_TABLE_ROWS_HTML": "".join(table_rows),
        "INSIGHTS_HEADING": "Mẫu chủ đề và hook",
        "LEFT_CARD_HEADING": "Chủ đề xuất hiện nhiều",
        "LEFT_CARD_CONTENT_HTML": counter_html(topic_source),
        "RIGHT_CARD_HEADING": "Hook xuất hiện nhiều",
        "RIGHT_CARD_CONTENT_HTML": counter_html(hook_counter),
        "RECOMMENDATIONS_HEADING": "Đề xuất áp dụng",
        "RECOMMENDATION_ITEMS_HTML": "".join(recommendations),
        "LIMITATIONS_LABEL": "Giới hạn:",
        "LIMITATIONS_HTML": " ".join(escape(item) for item in limitations),
        "ATTACHMENT_SUMMARY_HTML": escape(
            f"File Excel đính kèm: {workbook_path.name}; gồm 7 sheet dữ liệu và phân tích."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(replace_template(template, values), encoding="utf-8")

    text_lines = [
        f"BÁO CÁO PHÂN TÍCH ĐỐI THỦ YOUTUBE – {channel_title}",
        "",
        f"Khảo sát: {len(rows)} video công khai ngày {report_date}",
        f"Tổng views: {format_number(all_stats.get('total'))}",
        f"Trung bình: {format_number(mean_views)}; median: {format_number(median_views)}",
        f"Cao nhất: {format_number(all_stats.get('max'))}",
        f"Chủ đề nổi bật: {topic_summary}",
        f"Hook nổi bật: {hook_summary}",
        f"Top 10 chiếm {str(top_ten_share).replace('.', ',')}% tổng views",
        "",
        "Dữ liệu công khai; nhãn chủ đề/hook là mã hóa theo cấu hình và không chứng minh quan hệ nhân quả.",
        f"File Excel đính kèm: {workbook_path.name}",
    ]
    return output_path, "\n".join(text_lines)
