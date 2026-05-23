from sdk.tools import tool


@tool("query_product_stock", "查询商品实时库存和近30天销量", {"sku_id": str})
async def query_product_stock(args: dict) -> dict:
    sku_id = args["sku_id"]
    return {"sku_id": sku_id, "stock": 500, "sales_30d": 120, "source": "simulated"}


@tool("check_campaign_conflict", "检查商品是否存在互斥活动冲突", {"sku_id": str, "target_campaign": str})
async def check_campaign_conflict(args: dict) -> dict:
    return {"sku_id": args["sku_id"], "conflicts": [], "can_join": True}
