"""RAG 检索质量评估：内置标注样例 → recall@k 报告（hybrid vs vector-only 对比）。

用法（需 MySQL/Redis/Qdrant 服务）：
    python scripts/rag_eval.py            # 打印 markdown 报告
    python scripts/rag_eval.py --write    # 同时写入 docs/rag-eval.md
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.rag import search_chunks  # noqa: E402
from app.services.rag.embeddings import embed_texts  # noqa: E402
from app.services.rag.ingest import ingest_file  # noqa: E402
from app.services.rag.store import ensure_collection, search_points  # noqa: E402

EVAL_DOCS = [
    (
        "eval-doc-amox",
        "阿莫西林胶囊",
        """阿莫西林胶囊说明书

【药品名称】阿莫西林胶囊（Amoxicillin Capsules）

【药理作用】阿莫西林属于青霉素类广谱抗生素，通过抑制细菌细胞壁合成发挥杀菌作用，
对革兰氏阳性菌和阴性菌均有杀灭效果。

【适应症】适用于敏感菌所致的呼吸道感染、泌尿道感染、皮肤软组织感染以及伤寒、
沙门菌感染等。

【用法用量】口服，成人一次0.5g（2粒），每8小时一次；儿童按体重每日20-40mg/kg，
分2-3次服用。

【不良反应】常见腹泻、恶心、皮疹；偶见过敏性休克、血清病样反应。

【禁忌】对青霉素类药物过敏者禁用；有哮喘、湿疹、花粉症等过敏性疾病史者慎用；
严重肝肾功能不全者慎用。

【药物相互作用】丙磺舒可延长阿莫西林排泄；与氨基糖苷类联用有协同作用。"""),
    (
        "eval-doc-ibu",
        "布洛芬缓释胶囊",
        """布洛芬缓释胶囊说明书

【药品名称】布洛芬缓释胶囊（Ibuprofen Sustained-release Capsules）

【药理作用】布洛芬是非甾体抗炎药（NSAID），通过抑制环氧化酶减少前列腺素合成，
发挥解热、镇痛、抗炎作用。

【适应症】用于缓解轻至中度疼痛，如头痛、关节痛、偏头痛、牙痛、肌肉痛、神经痛、
痛经；也用于普通感冒或流行性感冒引起的发热。

【用法用量】口服，成人一次0.3-0.4g（1粒），一日2次（早晚各一次），整粒吞服。

【不良反应】常见恶心、呕吐、胃灼热、消化不良；偶见胃溃疡、转氨酶升高、
头晕、皮疹。

【禁忌】活动性消化道溃疡或胃肠道出血者禁用；对阿司匹林或其他非甾体抗炎药过敏者
禁用；妊娠晚期妇女禁用；重度心力衰竭患者禁用。

【注意事项】有胃溃疡病史者慎用；与抗凝药联用增加出血风险；不建议连用超过5天。"""),
    (
        "eval-doc-met",
        "盐酸二甲双胍片",
        """盐酸二甲双胍片说明书

【药品名称】盐酸二甲双胍片（Metformin Hydrochloride Tablets）

【药理作用】二甲双胍属于双胍类口服降糖药，通过减少肝糖输出、增加外周组织对
葡萄糖的利用、改善胰岛素敏感性而降低血糖，不刺激胰岛β细胞分泌，不引起低血糖。

【适应症】用于单纯饮食控制不满意的2型糖尿病病人，尤其是肥胖和伴高胰岛素
血症者；可与磺脲类或胰岛素合用治疗1型和2型糖尿病。

【用法用量】口服，开始一次0.25g，一日2-3次，餐中或餐后服用，以后根据血糖
调整剂量，一日最大剂量2.0g，分3次服用。

【不良反应】常见腹泻、恶心、呕吐、腹胀、消化不良、腹部不适；偶见维生素B12
缺乏、乳酸酸中毒。

【禁忌】肾功能不全、肝功能不全、严重感染、酸中毒、缺氧状态、酗酒者禁用；
造影检查前后48小时暂停用药；心力衰竭患者慎用。

【注意事项】服药期间定期检查肾功能与血乳酸水平；与胰岛素联用可减少胰岛素
用量；避免大量饮酒以防乳酸酸中毒。"""),
]

EVAL_CASES = [
    {"query": "阿莫西林有什么禁忌", "expect": "eval-doc-amox", "keywords": ["青霉素", "过敏"]},
    {"query": "青霉素过敏的人能吃阿莫西林吗", "expect": "eval-doc-amox", "keywords": ["青霉素"]},
    {"query": "阿莫西林是抗生素吗", "expect": "eval-doc-amox", "keywords": ["抗生素"]},
    {"query": "呼吸道感染吃什么消炎药", "expect": "eval-doc-amox", "keywords": ["呼吸道感染"]},
    {"query": "发烧吃布洛芬可以吗", "expect": "eval-doc-ibu", "keywords": ["发热", "解热"]},
    {"query": "胃溃疡能吃布洛芬吗", "expect": "eval-doc-ibu", "keywords": ["溃疡", "禁用"]},
    {"query": "布洛芬是止痛药吗", "expect": "eval-doc-ibu", "keywords": ["镇痛", "疼痛"]},
    {"query": "非甾体抗炎药有什么", "expect": "eval-doc-ibu", "keywords": ["非甾体", "布洛芬"]},
    {
        "query": "糖尿病吃二甲双胍要注意什么",
        "expect": "eval-doc-met",
        "keywords": ["糖尿病", "血糖"],
    },
    {"query": "肾功能不全能用二甲双胍吗", "expect": "eval-doc-met", "keywords": ["肾功能", "禁用"]},
    {"query": "二甲双胍会引起低血糖吗", "expect": "eval-doc-met", "keywords": ["低血糖"]},
    {"query": "降糖药二甲双胍怎么服用", "expect": "eval-doc-met", "keywords": ["降糖", "口服"]},
]


def ingest_eval_docs() -> None:
    import tempfile

    ensure_collection()
    for doc_id, drug_name, text in EVAL_DOCS:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".txt", encoding="utf-8", delete=False
        ) as f:
            f.write(text)
            path = f.name
        ingest_file(doc_id, drug_name, path)
        Path(path).unlink(missing_ok=True)


def vector_only_topk(query: str, k: int = 5) -> list[str]:
    vector = embed_texts([query])[0]
    points = search_points(vector, k)
    return [p.payload.get("doc_id", "") for p in points if p.payload]


def evaluate(cases: list[dict], k: int = 5) -> dict:
    rows = []
    hybrid_hit = vector_hit = keyword_hit = 0
    for case in cases:
        results = search_chunks(case["query"], top_k=k)
        hybrid_rank = next(
            (idx + 1 for idx, r in enumerate(results) if r["docId"] == case["expect"]), 0
        )
        vec_docs = vector_only_topk(case["query"], k)
        vector_rank = (
            vec_docs.index(case["expect"]) + 1 if case["expect"] in vec_docs else 0
        )
        blob = " ".join(r["chunkContent"] for r in results)
        kw_found = sum(1 for kw in case["keywords"] if kw in blob)
        hybrid_hit += hybrid_rank > 0
        vector_hit += vector_rank > 0
        keyword_hit += kw_found >= max(1, len(case["keywords"]))
        rows.append(
            {
                "query": case["query"],
                "hybrid_rank": hybrid_rank,
                "vector_rank": vector_rank,
                "keyword": f"{kw_found}/{len(case['keywords'])}",
            }
        )
    n = len(cases)
    return {
        "rows": rows,
        "n": n,
        "hybrid_recall": hybrid_hit / n,
        "vector_recall": vector_hit / n,
        "keyword_rate": keyword_hit / n,
    }


def to_markdown(report: dict) -> str:
    lines = [
        "# RAG 检索质量评估报告",
        "",
        f"- 样例文档：{len(EVAL_DOCS)} 份（阿莫西林 / 布洛芬 / 二甲双胍）",
        f"- 评估用例：{report['n']} 条",
        f"- 混合检索 recall@5：**{report['hybrid_recall']:.1%}**",
        f"- 纯向量 recall@5：{report['vector_recall']:.1%}",
        f"- 关键词完整命中率：{report['keyword_rate']:.1%}",
        "",
        "| # | query | 混合@5排名 | 纯向量@5排名 | 关键词 |",
        "|---|-------|-----------|-------------|--------|",
    ]
    for i, row in enumerate(report["rows"], 1):
        h = row["hybrid_rank"] or "miss"
        v = row["vector_rank"] or "miss"
        lines.append(f"| {i} | {row['query']} | {h} | {v} | {row['keyword']} |")
    lines += [
        "",
        "> 评估方式：ingest 内置 3 份样例说明书，逐条执行在线检索链路（query 改写关闭：",
        "> history 为空），hybrid 为 BM25+向量 RRF 融合结果，纯向量为向量召回 top5。",
        "> 关键词命中指 top5 片段中包含标注关键词。CI 中以缩减用例（test_rag_eval.py）",
        "> 断言 hybrid recall@5 ≥ 0.8 作为质量门禁。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG 检索质量评估")
    parser.add_argument("--write", action="store_true", help="写入 docs/rag-eval.md")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    print("ingest eval docs ...", flush=True)
    ingest_eval_docs()
    print(f"evaluating {len(EVAL_CASES)} cases ...", flush=True)
    report = evaluate(EVAL_CASES, k=args.k)
    md = to_markdown(report)
    print(md)
    if args.write:
        (ROOT / "docs" / "rag-eval.md").write_text(md, encoding="utf-8")
        print("written: docs/rag-eval.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
