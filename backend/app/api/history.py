"""History & Project API."""
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from ..models.schemas import HistoryItem, HistoryDetail, DeleteResponse, TaskCreateResponse
from ..services.agent import (
    create_task,
    get_history,
    get_history_detail,
    delete_task,
    add_message,
    rename_task,
    create_project,
    get_projects,
    rename_project,
)

router = APIRouter(prefix="/api", tags=["history"])


class SaveMessageRequest(BaseModel):
    role: str
    content: str
    msg_metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata")


# --- Messages ---

@router.post("/history/{task_id}/message")
async def save_message(task_id: str, body: SaveMessageRequest):
    ok = add_message(task_id, body.role, body.content, body.msg_metadata)
    if not ok:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"success": True}


# --- Tasks ---

@router.post("/task/new")
async def new_task(project_id: str = Query(default="default")):
    return create_task(project_id)


@router.get("/history")
async def list_history(project_id: str = Query(default=None)):
    return get_history(project_id if project_id else None)


@router.get("/history/{task_id}")
async def get_task_history(task_id: str):
    detail = get_history_detail(task_id)
    if not detail:
        raise HTTPException(status_code=404, detail="任务不存在")
    return detail


@router.delete("/history/{task_id}")
async def remove_history(task_id: str):
    if delete_task(task_id):
        return DeleteResponse(success=True, message="删除成功")
    raise HTTPException(status_code=404, detail="任务不存在")


# --- Projects ---

@router.get("/projects")
async def list_projects():
    return get_projects()


@router.post("/projects")
async def new_project(name: str = Query(default="新项目")):
    return create_project(name)


@router.put("/projects/{project_id}/rename")
async def rename_project_route(project_id: str, name: str = Query(...)):
    if not rename_project(project_id, name):
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"success": True}


@router.put("/history/{task_id}/rename")
async def rename_task_route(task_id: str, name: str = Query(...)):
    if not rename_task(task_id, name):
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"success": True}


# --- Products ---

_SKU_CATALOG = [
    # 足金/千足金
    {"sku_id":"CTF-FJ-999-001","product_name":"足金999古法金手镯25g","brand":"CTF 传承","category_l1":"黄金","category_l2":"古法金","pricing_model":"weight","weight_g":25.0,"purity":"999","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":19800,"list_price_rmb":18800,"last_30d_min_price":18200,"last_90d_min_price":17800,"last_365d_min_price":16500,"stock":320,"last_90d_sales":158,"review_rate":0.985,"return_rate":0.012,"new_product":False,"certificate_ids":[],"factory_id":"F-SZ-001","lead_time_days":7,"active_campaigns":["tmall:2025_618"]},
    {"sku_id":"CTF-FJ-999-002","product_name":"足金999福字吊坠3.5g","brand":"CTF","category_l1":"黄金","category_l2":"足金","pricing_model":"weight","weight_g":3.5,"purity":"999","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":2880,"list_price_rmb":2680,"last_30d_min_price":2580,"last_90d_min_price":2480,"last_365d_min_price":2350,"stock":1800,"last_90d_sales":1024,"review_rate":0.978,"return_rate":0.025,"new_product":False,"certificate_ids":[],"factory_id":"F-SZ-002","lead_time_days":5,"active_campaigns":[]},
    {"sku_id":"CTF-FJ-999-003","product_name":"足金999.9婚嫁三件套18g","brand":"CTF","category_l1":"黄金","category_l2":"千足金","pricing_model":"weight","weight_g":18.0,"purity":"999.9","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":14800,"list_price_rmb":14000,"last_30d_min_price":13500,"last_90d_min_price":13200,"last_365d_min_price":12800,"stock":280,"last_90d_sales":95,"review_rate":0.98,"return_rate":0.018,"new_product":False,"certificate_ids":[],"factory_id":"F-SZ-001","lead_time_days":10,"active_campaigns":["tmall:2025_brandday"]},
    {"sku_id":"CTF-FJ-999-004","product_name":"足金999婴儿手镯5.5g","brand":"CTF","category_l1":"黄金","category_l2":"足金","pricing_model":"weight","weight_g":5.5,"purity":"999","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":4380,"list_price_rmb":4180,"last_30d_min_price":4080,"last_90d_min_price":3980,"last_365d_min_price":3850,"stock":600,"last_90d_sales":312,"review_rate":0.99,"return_rate":0.005,"new_product":False,"certificate_ids":[],"factory_id":"F-SZ-002","lead_time_days":5,"active_campaigns":[]},
    {"sku_id":"CTF-FJ-9999-001","product_name":"万足金999.99投资金条50g","brand":"CTF","category_l1":"黄金","category_l2":"万足金","pricing_model":"weight","weight_g":50.0,"purity":"999.99","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":38800,"list_price_rmb":None,"last_30d_min_price":None,"last_90d_min_price":None,"last_365d_min_price":None,"stock":120,"last_90d_sales":45,"review_rate":0.995,"return_rate":0.002,"new_product":False,"certificate_ids":[],"factory_id":"F-SH-003","lead_time_days":14,"active_campaigns":[]},
    # 5G黄金/硬足金
    {"sku_id":"CTF-5G-001","product_name":"5G黄金小蛮腰耳钉1.2g","brand":"CTF","category_l1":"黄金","category_l2":"5G黄金","pricing_model":"fixed","weight_g":1.2,"purity":"999","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":1380,"list_price_rmb":1280,"last_30d_min_price":1180,"last_90d_min_price":1080,"last_365d_min_price":980,"stock":2400,"last_90d_sales":1850,"review_rate":0.982,"return_rate":0.015,"new_product":True,"certificate_ids":[],"factory_id":"F-SZ-002","lead_time_days":3,"active_campaigns":[]},
    {"sku_id":"CTF-5G-002","product_name":"5G黄金转运珠手链2.8g","brand":"CTF","category_l1":"黄金","category_l2":"5G黄金","pricing_model":"fixed","weight_g":2.8,"purity":"999","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":2680,"list_price_rmb":2480,"last_30d_min_price":2380,"last_90d_min_price":2280,"last_365d_min_price":2180,"stock":1800,"last_90d_sales":920,"review_rate":0.975,"return_rate":0.028,"new_product":True,"certificate_ids":[],"factory_id":"F-SZ-002","lead_time_days":3,"active_campaigns":["tmall:2025_618"]},
    {"sku_id":"CTF-HG-001","product_name":"硬足金福字吊坠1.5g","brand":"CTF","category_l1":"黄金","category_l2":"硬足金","pricing_model":"fixed","weight_g":1.5,"purity":"999","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":1580,"list_price_rmb":1480,"last_30d_min_price":1380,"last_90d_min_price":1280,"last_365d_min_price":1180,"stock":1500,"last_90d_sales":780,"review_rate":0.988,"return_rate":0.011,"new_product":False,"certificate_ids":[],"factory_id":"F-SZ-002","lead_time_days":5,"active_campaigns":[]},
    {"sku_id":"CTF-GFJ-001","product_name":"古法金传承福手镯22g","brand":"CTF 传承","category_l1":"黄金","category_l2":"古法金","pricing_model":"fixed","weight_g":22.0,"purity":"999","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":23800,"list_price_rmb":22800,"last_30d_min_price":22000,"last_90d_min_price":21500,"last_365d_min_price":20800,"stock":220,"last_90d_sales":75,"review_rate":0.991,"return_rate":0.008,"new_product":True,"certificate_ids":[],"factory_id":"F-SZ-001","lead_time_days":10,"active_campaigns":["tmall:2025_brandday"]},
    # K金/镶嵌钻饰
    {"sku_id":"CTF-G18K-NL-001","product_name":"周大福18K金项链0.50ct","brand":"CTF","category_l1":"镶嵌","category_l2":"K金","pricing_model":"fixed","weight_g":6.5,"purity":"Au750","gem_carat":0.5,"gem_color":"F","gem_clarity":"VS1","gem_cut":"EX","tag_price_rmb":28800,"list_price_rmb":27800,"last_30d_min_price":26800,"last_90d_min_price":26000,"last_365d_min_price":25500,"stock":60,"last_90d_sales":32,"review_rate":0.98,"return_rate":0.02,"new_product":False,"certificate_ids":["CTF-GIA-001"],"factory_id":"F-SH-002","lead_time_days":14,"active_campaigns":[]},
    {"sku_id":"CTF-G18K-NL-002","product_name":"周大福18K金项链0.30ct","brand":"CTF","category_l1":"镶嵌","category_l2":"K金","pricing_model":"fixed","weight_g":5.2,"purity":"Au750","gem_carat":0.3,"gem_color":"G","gem_clarity":"VS2","gem_cut":"EX","tag_price_rmb":18800,"list_price_rmb":17800,"last_30d_min_price":16800,"last_90d_min_price":16000,"last_365d_min_price":15500,"stock":80,"last_90d_sales":48,"review_rate":0.978,"return_rate":0.018,"new_product":False,"certificate_ids":["CTF-GIA-002"],"factory_id":"F-SH-002","lead_time_days":14,"active_campaigns":["tmall:2025_brandday"]},
    {"sku_id":"CTF-G18K-RG-001","product_name":"周大福18K金钻戒0.20ct","brand":"SOINLOVE","category_l1":"镶嵌","category_l2":"求婚钻戒","pricing_model":"fixed","weight_g":3.5,"purity":"Au750","gem_carat":0.2,"gem_color":"H","gem_clarity":"SI1","gem_cut":"VG","tag_price_rmb":9880,"list_price_rmb":9380,"last_30d_min_price":8980,"last_90d_min_price":8780,"last_365d_min_price":8580,"stock":150,"last_90d_sales":96,"review_rate":0.982,"return_rate":0.015,"new_product":True,"certificate_ids":["CTF-GIA-003"],"factory_id":"F-SH-002","lead_time_days":14,"active_campaigns":["jd:2025_brandday"]},
    {"sku_id":"CTF-G18K-RG-002","product_name":"T MARK 30分钻戒","brand":"T MARK","category_l1":"镶嵌","category_l2":"求婚钻戒","pricing_model":"fixed","weight_g":3.8,"purity":"Au750","gem_carat":0.3,"gem_color":"F","gem_clarity":"VVS2","gem_cut":"EX","tag_price_rmb":22800,"list_price_rmb":21800,"last_30d_min_price":20800,"last_90d_min_price":20200,"last_365d_min_price":19800,"stock":80,"last_90d_sales":52,"review_rate":0.99,"return_rate":0.01,"new_product":True,"certificate_ids":["CTF-TMARK-001"],"factory_id":"F-SH-002","lead_time_days":14,"active_campaigns":[]},
    {"sku_id":"CTF-PT950-RG-001","product_name":"铂金Pt950 50分钻戒","brand":"CTF","category_l1":"镶嵌","category_l2":"求婚钻戒","pricing_model":"fixed","weight_g":4.2,"purity":"Pt950","gem_carat":0.5,"gem_color":"E","gem_clarity":"VVS1","gem_cut":"EX","tag_price_rmb":38800,"list_price_rmb":36800,"last_30d_min_price":35800,"last_90d_min_price":34800,"last_365d_min_price":33800,"stock":40,"last_90d_sales":18,"review_rate":0.985,"return_rate":0.012,"new_product":False,"certificate_ids":["CTF-GIA-004"],"factory_id":"F-SH-002","lead_time_days":21,"active_campaigns":[]},
    {"sku_id":"CTF-G18K-EAR-001","product_name":"18K金钻石耳钉0.10ct一对","brand":"CTF","category_l1":"镶嵌","category_l2":"耳饰","pricing_model":"fixed","weight_g":1.8,"purity":"Au750","gem_carat":0.1,"gem_color":"G","gem_clarity":"VS2","gem_cut":"EX","tag_price_rmb":4880,"list_price_rmb":4680,"last_30d_min_price":4480,"last_90d_min_price":4280,"last_365d_min_price":4180,"stock":320,"last_90d_sales":195,"review_rate":0.98,"return_rate":0.018,"new_product":False,"certificate_ids":[],"factory_id":"F-SH-002","lead_time_days":7,"active_campaigns":[]},
    # 翡翠/玉石
    {"sku_id":"CTF-JADE-001","product_name":"翡翠A货平安无事牌吊坠","brand":"CTF","category_l1":"玉石","category_l2":"翡翠","pricing_model":"fixed","weight_g":None,"purity":None,"gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":18800,"list_price_rmb":17800,"last_30d_min_price":17000,"last_90d_min_price":16500,"last_365d_min_price":16000,"stock":30,"last_90d_sales":12,"review_rate":0.97,"return_rate":0.035,"new_product":False,"certificate_ids":["CTF-JADE-001"],"factory_id":"F-GZ-001","lead_time_days":21,"active_campaigns":[]},
    {"sku_id":"CTF-JADE-002","product_name":"翡翠A货福豆挂坠","brand":"CTF","category_l1":"玉石","category_l2":"翡翠","pricing_model":"fixed","weight_g":None,"purity":None,"gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":5880,"list_price_rmb":5580,"last_30d_min_price":5380,"last_90d_min_price":5180,"last_365d_min_price":4980,"stock":80,"last_90d_sales":38,"review_rate":0.975,"return_rate":0.028,"new_product":True,"certificate_ids":["CTF-JADE-002"],"factory_id":"F-GZ-001","lead_time_days":21,"active_campaigns":[]},
    # 珍珠
    {"sku_id":"CTF-PEARL-001","product_name":"Akoya海水珍珠项链7-8mm","brand":"MONOLOGUE","category_l1":"珍珠","category_l2":"海水珍珠","pricing_model":"fixed","weight_g":None,"purity":None,"gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":6880,"list_price_rmb":6580,"last_30d_min_price":6280,"last_90d_min_price":6080,"last_365d_min_price":5880,"stock":120,"last_90d_sales":65,"review_rate":0.98,"return_rate":0.02,"new_product":False,"certificate_ids":[],"factory_id":"F-SH-004","lead_time_days":14,"active_campaigns":[]},
    {"sku_id":"CTF-PEARL-002","product_name":"大溪地黑珍珠吊坠9-10mm","brand":"MONOLOGUE","category_l1":"珍珠","category_l2":"海水珍珠","pricing_model":"fixed","weight_g":None,"purity":None,"gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":12800,"list_price_rmb":12000,"last_30d_min_price":11500,"last_90d_min_price":11200,"last_365d_min_price":10800,"stock":50,"last_90d_sales":22,"review_rate":0.985,"return_rate":0.015,"new_product":True,"certificate_ids":[],"factory_id":"F-SH-004","lead_time_days":21,"active_campaigns":[]},
    # 铂金/银饰
    {"sku_id":"CTF-PT-NL-001","product_name":"铂金Pt950项链5.5g","brand":"CTF","category_l1":"铂金","category_l2":"项链","pricing_model":"weight","weight_g":5.5,"purity":"Pt950","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":5680,"list_price_rmb":5380,"last_30d_min_price":5180,"last_90d_min_price":4980,"last_365d_min_price":4780,"stock":240,"last_90d_sales":132,"review_rate":0.982,"return_rate":0.018,"new_product":False,"certificate_ids":[],"factory_id":"F-SH-001","lead_time_days":7,"active_campaigns":[]},
    {"sku_id":"CTF-PT-RG-001","product_name":"铂金Pt950素圈对戒","brand":"CTF","category_l1":"铂金","category_l2":"戒指","pricing_model":"weight","weight_g":3.2,"purity":"Pt950","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":6880,"list_price_rmb":6480,"last_30d_min_price":6280,"last_90d_min_price":6080,"last_365d_min_price":5880,"stock":180,"last_90d_sales":88,"review_rate":0.98,"return_rate":0.022,"new_product":False,"certificate_ids":[],"factory_id":"F-SH-001","lead_time_days":7,"active_campaigns":[]},
    {"sku_id":"CTF-SLV-001","product_name":"925银转运珠手链","brand":"CTF","category_l1":"银饰","category_l2":"手链","pricing_model":"fixed","weight_g":4.5,"purity":"925","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":580,"list_price_rmb":480,"last_30d_min_price":380,"last_90d_min_price":350,"last_365d_min_price":320,"stock":1500,"last_90d_sales":880,"review_rate":0.975,"return_rate":0.03,"new_product":True,"certificate_ids":[],"factory_id":"F-SZ-003","lead_time_days":3,"active_campaigns":[]},
    # 投资金
    {"sku_id":"CTF-INV-001","product_name":"Au999.9投资金条100g","brand":"CTF","category_l1":"黄金","category_l2":"投资金","pricing_model":"weight","weight_g":100.0,"purity":"999.9","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":75800,"list_price_rmb":None,"last_30d_min_price":None,"last_90d_min_price":None,"last_365d_min_price":None,"stock":60,"last_90d_sales":28,"review_rate":0.995,"return_rate":0.001,"new_product":False,"certificate_ids":[],"factory_id":"F-SH-003","lead_time_days":14,"active_campaigns":[]},
    {"sku_id":"CTF-INV-002","product_name":"Au999.9投资金条20g","brand":"CTF","category_l1":"黄金","category_l2":"投资金","pricing_model":"weight","weight_g":20.0,"purity":"999.9","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":15400,"list_price_rmb":None,"last_30d_min_price":None,"last_90d_min_price":None,"last_365d_min_price":None,"stock":200,"last_90d_sales":132,"review_rate":0.995,"return_rate":0.001,"new_product":False,"certificate_ids":[],"factory_id":"F-SH-003","lead_time_days":14,"active_campaigns":[]},
    # LOLA/SOINLOVE/国潮
    {"sku_id":"CTF-SL-RG-001","product_name":"SOINLOVE双心钻戒0.20ct","brand":"SOINLOVE","category_l1":"镶嵌","category_l2":"求婚钻戒","pricing_model":"fixed","weight_g":3.5,"purity":"Au750","gem_carat":0.2,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":12800,"list_price_rmb":11800,"last_30d_min_price":11000,"last_90d_min_price":10500,"last_365d_min_price":10000,"stock":200,"last_90d_sales":158,"review_rate":0.985,"return_rate":0.015,"new_product":True,"certificate_ids":[],"factory_id":"F-SH-002","lead_time_days":14,"active_campaigns":["jd:2025_brandday"]},
    {"sku_id":"CTF-ML-NL-001","product_name":"MONOLOGUE月光石锁骨链","brand":"MONOLOGUE","category_l1":"镶嵌","category_l2":"项链","pricing_model":"fixed","weight_g":1.8,"purity":"Au750","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":2880,"list_price_rmb":2680,"last_30d_min_price":2480,"last_90d_min_price":2380,"last_365d_min_price":2280,"stock":480,"last_90d_sales":252,"review_rate":0.978,"return_rate":0.025,"new_product":True,"certificate_ids":[],"factory_id":"F-SH-002","lead_time_days":7,"active_campaigns":[]},
    {"sku_id":"CTF-IP-001","product_name":"国潮系列长安金吊坠","brand":"CTF 传承","category_l1":"黄金","category_l2":"古法金","pricing_model":"fixed","weight_g":4.5,"purity":"999","gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,"tag_price_rmb":4880,"list_price_rmb":4580,"last_30d_min_price":4380,"last_90d_min_price":4280,"last_365d_min_price":4180,"stock":320,"last_90d_sales":188,"review_rate":0.982,"return_rate":0.018,"new_product":True,"certificate_ids":[],"factory_id":"F-SZ-001","lead_time_days":10,"active_campaigns":["tmall:2025_brandday"]},
]

# Make products mutable for CRUD
_products = list(_SKU_CATALOG)


@router.get("/products")
async def list_products(category_l1: str = Query(default=None), search: str = Query(default=None)):
    """List products from SKU catalog."""
    result = _products
    if category_l1:
        result = [p for p in result if p["category_l1"] == category_l1]
    if search:
        q = search.lower()
        result = [p for p in result if q in p["product_name"].lower() or q in p["sku_id"].lower() or q in p["brand"].lower()]
    cats = sorted(set(p["category_l1"] for p in _products))
    return {"products": result, "categories": cats, "total": len(_products)}


@router.post("/products")
async def add_product(product: dict):
    """Add a new product to the catalog."""
    if "sku_id" not in product or not product["sku_id"]:
        raise HTTPException(status_code=400, detail="sku_id is required")
    if any(p["sku_id"] == product["sku_id"] for p in _products):
        raise HTTPException(status_code=409, detail="SKU already exists")
    defaults = {
        "sku_id":"","product_name":"","brand":"","category_l1":"","category_l2":"","pricing_model":"fixed",
        "weight_g":None,"purity":None,"gem_carat":None,"gem_color":None,"gem_clarity":None,"gem_cut":None,
        "tag_price_rmb":0,"list_price_rmb":None,"last_30d_min_price":None,"last_90d_min_price":None,"last_365d_min_price":None,
        "stock":0,"last_90d_sales":0,"review_rate":0.0,"return_rate":0.0,
        "new_product":True,"certificate_ids":[],"factory_id":"","lead_time_days":7,"active_campaigns":[],
    }
    new_p = {**defaults, **product}
    _products.append(new_p)
    return {"success": True, "product": new_p}


@router.delete("/products/{sku_id}")
async def delete_product(sku_id: str):
    """Delete a product from the catalog."""
    global _products
    before = len(_products)
    _products = [p for p in _products if p["sku_id"] != sku_id]
    if len(_products) == before:
        raise HTTPException(status_code=404, detail="SKU not found")
    return {"success": True}


# --- Summarize ---

@router.post("/history/{task_id}/summarize")
async def summarize_task(task_id: str):
    from ..services.llm import summarize_task_messages
    detail = get_history_detail(task_id)
    if not detail:
        raise HTTPException(status_code=404, detail="任务不存在")
    summary = await summarize_task_messages(detail["messages"])
    return summary


@router.post("/projects/{project_id}/summarize")
async def summarize_project(project_id: str):
    """Summarize ALL tasks within a project."""
    from ..services.llm import summarize_project_tasks
    from ..services.agent import get_history
    tasks = get_history(project_id)
    all_messages = []
    for t in tasks:
        detail = get_history_detail(t["task_id"])
        if detail:
            all_messages.extend(detail["messages"])
    if not all_messages:
        return {"title": "无对话", "rule_points": [], "recommendations": [], "checks": [], "risks": []}
    return await summarize_project_tasks(all_messages, len(tasks))
