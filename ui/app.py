from __future__ import annotations

from typing import Any

import streamlit as st

from agent import chat, database
from agent.llm import model_status


st.set_page_config(page_title="执行辅助 Agent", layout="wide")
database.init_db()
database.seed_sample_catalog()


@st.cache_data(ttl=3, show_spinner=False)
def cached_projects() -> list[dict[str, Any]]:
    return database.list_projects()


@st.cache_data(ttl=3, show_spinner=False)
def cached_conversations(project_id: str) -> list[dict[str, Any]]:
    return database.list_conversations(project_id)


@st.cache_data(ttl=3, show_spinner=False)
def cached_messages(conversation_id: str) -> list[dict[str, Any]]:
    return database.list_conversation_messages(conversation_id)


@st.cache_data(ttl=3, show_spinner=False)
def cached_listing(project_id: str) -> list[dict[str, Any]]:
    return database.list_listing_items(project_id)


def clear_cached_reads() -> None:
    st.cache_data.clear()


def ensure_workspace() -> tuple[list[dict[str, Any]], str, str]:
    projects = cached_projects()
    if not projects:
        project_id = database.create_project("默认项目", "系统自动创建的默认项目")
        conversation_id = database.create_conversation(project_id, "默认对话")
        clear_cached_reads()
        return cached_projects(), project_id, conversation_id

    project_ids = {item["id"] for item in projects}
    project_id = st.session_state.get("project_id")
    if project_id not in project_ids:
        project_id = projects[0]["id"]
        st.session_state.project_id = project_id

    conversations = cached_conversations(project_id)
    if not conversations:
        conversation_id = database.create_conversation(project_id, "默认对话")
        clear_cached_reads()
        conversations = cached_conversations(project_id)
    else:
        conversation_id = st.session_state.get("conversation_id")
        if conversation_id not in {item["id"] for item in conversations}:
            conversation_id = conversations[0]["id"]

    st.session_state.project_id = project_id
    st.session_state.conversation_id = conversation_id
    return projects, project_id, conversation_id


if "project_id" not in st.session_state:
    st.session_state.project_id = None
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "page" not in st.session_state:
    st.session_state.page = "workspace"
if "editing_product_id" not in st.session_state:
    st.session_state.editing_product_id = None

projects, project_id, conversation_id = ensure_workspace()
status = model_status()

with st.sidebar:
    st.title("执行辅助 Agent")
    st.caption(f"模型：{status.get('model')}")
    st.caption(f"数据库：{database.get_db_path()}")

    st.divider()
    st.subheader("导航")
    nav_choice = st.radio(
        "页面",
        ["项目工作台", "SKU 品类库"],
        index=0 if st.session_state.page == "workspace" else 1,
        label_visibility="collapsed",
    )
    new_page = "workspace" if nav_choice == "项目工作台" else "products"
    if new_page != st.session_state.page:
        st.session_state.page = new_page
        st.rerun()

if st.session_state.page == "products":
    st.header("SKU 品类库")
    st.caption("统一维护 SKU 主数据。SKU 编号自动生成，字段结构参考 ERP 输出。")

    query = st.text_input("搜索商品", placeholder="输入商品编号、名称、品类、品牌或 SKU")
    products = database.list_catalog_products(query)

    left, right = st.columns([0.56, 0.44], gap="large")
    with left:
        st.subheader("商品列表")
        if not products:
            st.info("暂无商品。")
        else:
            table_rows = [
                {
                    "SKU编号": item["sku_id"],
                    "商品名称": item["product_name"],
                    "一级类目": item["category_l1"],
                    "二级类目": item["category_l2"],
                    "品牌": item["brand"],
                    "定价": item["pricing_model"],
                    "活动价": item["list_price_rmb"],
                    "库存": item["stock"],
                    "90天销量": item["last_90d_sales"],
                    "状态": item["status"],
                }
                for item in products
            ]
            st.dataframe(table_rows, use_container_width=True, hide_index=True)

            product_options = {f"{item['sku_id']} - {item['product_name']}": item["id"] for item in products}
            selected_product = st.selectbox("选择要编辑的 SKU", [""] + list(product_options.keys()))
            if selected_product:
                st.session_state.editing_product_id = product_options[selected_product]

    editing_product = (
        database.get_catalog_product(st.session_state.editing_product_id)
        if st.session_state.editing_product_id
        else None
    )

    with right:
        st.subheader("商品信息")
        if editing_product:
            st.caption(f"正在编辑：{editing_product['sku_id']}")
        else:
            st.caption("新增商品时自动生成 SKU 编号")

        with st.form("product_form", clear_on_submit=False):
            product_name = st.text_input("商品名称", value=(editing_product or {}).get("product_name", ""))
            brand = st.text_input("品牌", value=(editing_product or {}).get("brand", ""))
            col_cat_1, col_cat_2 = st.columns(2)
            with col_cat_1:
                category_l1 = st.selectbox(
                    "一级类目",
                    ["黄金", "镶嵌", "铂金", "银饰", "玉石", "珍珠", "其他"],
                    index=["黄金", "镶嵌", "铂金", "银饰", "玉石", "珍珠", "其他"].index((editing_product or {}).get("category_l1", "黄金")) if (editing_product or {}).get("category_l1", "黄金") in ["黄金", "镶嵌", "铂金", "银饰", "玉石", "珍珠", "其他"] else 0,
                )
            with col_cat_2:
                category_l2 = st.text_input("二级类目", value=(editing_product or {}).get("category_l2", ""))
            pricing_model = st.selectbox(
                "定价模式",
                ["fixed", "weight"],
                index=0 if (editing_product or {}).get("pricing_model", "fixed") == "fixed" else 1,
            )
            col_a, col_b = st.columns(2)
            with col_a:
                weight_g = st.number_input("克重(g)", min_value=0.0, value=float((editing_product or {}).get("weight_g", 0) or 0), step=0.1)
                purity = st.text_input("成色", value=(editing_product or {}).get("purity", ""))
                tag_price_rmb = st.number_input("吊牌价", min_value=0.0, value=float((editing_product or {}).get("tag_price_rmb", 0) or 0), step=1.0)
                list_price_rmb = st.number_input("划线/活动价", min_value=0.0, value=float((editing_product or {}).get("list_price_rmb", 0) or 0), step=1.0)
                stock = st.number_input("库存", min_value=0, value=int((editing_product or {}).get("stock", 0) or 0), step=1)
            with col_b:
                last_30d_min_price = st.number_input("近30天最低价", min_value=0.0, value=float((editing_product or {}).get("last_30d_min_price", 0) or 0), step=1.0)
                last_90d_min_price = st.number_input("近90天最低价", min_value=0.0, value=float((editing_product or {}).get("last_90d_min_price", 0) or 0), step=1.0)
                last_365d_min_price = st.number_input("近365天最低价", min_value=0.0, value=float((editing_product or {}).get("last_365d_min_price", 0) or 0), step=1.0)
                last_90d_sales = st.number_input("近90天销量", min_value=0, value=int((editing_product or {}).get("last_90d_sales", 0) or 0), step=1)
                review_rate = st.number_input("好评率(%)", min_value=0.0, max_value=100.0, value=float((editing_product or {}).get("review_rate", 0) or 0), step=0.1)

            with st.expander("镶嵌/供应链字段"):
                g1, g2, g3, g4 = st.columns(4)
                with g1:
                    gem_carat = st.number_input("主石ct", min_value=0.0, value=float((editing_product or {}).get("gem_carat", 0) or 0), step=0.01)
                with g2:
                    gem_color = st.text_input("颜色", value=(editing_product or {}).get("gem_color") or "")
                with g3:
                    gem_clarity = st.text_input("净度", value=(editing_product or {}).get("gem_clarity") or "")
                with g4:
                    gem_cut = st.text_input("切工", value=(editing_product or {}).get("gem_cut") or "")
                return_rate = st.number_input("退货率(%)", min_value=0.0, max_value=100.0, value=float((editing_product or {}).get("return_rate", 0) or 0), step=0.1)
                new_product = st.checkbox("近90天上新", value=bool((editing_product or {}).get("new_product", False)))
                certificate_ids_text = st.text_input("证书编号（逗号分隔）", value=", ".join((editing_product or {}).get("certificate_ids", [])))
                factory_id = st.text_input("工厂代码", value=(editing_product or {}).get("factory_id", ""))
                lead_time_days = st.number_input("补货周期(天)", min_value=0, value=int((editing_product or {}).get("lead_time_days", 0) or 0), step=1)
                active_campaigns_text = st.text_input("在售活动（逗号分隔）", value=", ".join((editing_product or {}).get("active_campaigns", [])))

            status_value = (editing_product or {}).get("status", "在售")
            statuses = ["在售", "待上架", "已下架", "缺货", "待确认"]
            status_index = statuses.index(status_value) if status_value in statuses else 0
            status = st.selectbox("状态", statuses, index=status_index)
            notes = st.text_area("备注", value=(editing_product or {}).get("notes", ""), height=100)
            submitted = st.form_submit_button("保存 SKU", type="primary", use_container_width=True)

        payload = {
            "product_name": product_name,
            "brand": brand,
            "category_l1": category_l1,
            "category_l2": category_l2,
            "pricing_model": pricing_model,
            "weight_g": weight_g if weight_g > 0 else None,
            "purity": purity,
            "gem_carat": gem_carat if gem_carat > 0 else None,
            "gem_color": gem_color or None,
            "gem_clarity": gem_clarity or None,
            "gem_cut": gem_cut or None,
            "tag_price_rmb": tag_price_rmb,
            "list_price_rmb": list_price_rmb,
            "last_30d_min_price": last_30d_min_price,
            "last_90d_min_price": last_90d_min_price,
            "last_365d_min_price": last_365d_min_price,
            "stock": stock,
            "last_90d_sales": last_90d_sales,
            "review_rate": review_rate,
            "return_rate": return_rate,
            "new_product": new_product,
            "certificate_ids": [item.strip() for item in certificate_ids_text.split(",") if item.strip()],
            "factory_id": factory_id,
            "lead_time_days": lead_time_days,
            "active_campaigns": [item.strip() for item in active_campaigns_text.split(",") if item.strip()],
            "status": status,
            "notes": notes,
        }
        if submitted:
            if not product_name.strip():
                st.warning("商品名称不能为空。")
            elif editing_product:
                database.update_catalog_product(editing_product["id"], payload)
                st.success("SKU 已更新。")
                st.rerun()
            else:
                product_id = database.create_catalog_product(payload)
                st.session_state.editing_product_id = product_id
                st.success("SKU 已创建。")
                st.rerun()

        if editing_product:
            c1, c2 = st.columns(2)
            if c1.button("新建空白 SKU", use_container_width=True):
                st.session_state.editing_product_id = None
                st.rerun()
            if c2.button("删除 SKU", use_container_width=True):
                database.delete_catalog_product(editing_product["id"])
                st.session_state.editing_product_id = None
                st.rerun()

    st.stop()

with st.sidebar:
    st.divider()
    st.subheader("项目")
    project_names = [item["name"] for item in projects]
    project_by_name = {item["name"]: item["id"] for item in projects}
    current_project = next(item for item in projects if item["id"] == project_id)
    selected_name = st.selectbox(
        "选择项目",
        project_names,
        index=project_names.index(current_project["name"]),
        label_visibility="collapsed",
    )
    selected_project_id = project_by_name[selected_name]
    if selected_project_id != project_id:
        st.session_state.project_id = selected_project_id
        st.session_state.conversation_id = None
        clear_cached_reads()
        st.rerun()

    with st.expander("新建项目"):
        with st.form("create_project_form", clear_on_submit=True):
            new_project_name = st.text_input("项目名称", placeholder="例如：618 大促")
            new_project_desc = st.text_area("项目说明", height=80)
            submitted = st.form_submit_button("创建项目", use_container_width=True)
        if submitted and new_project_name.strip():
            created_project_id = database.create_project(new_project_name, new_project_desc)
            created_conversation_id = database.create_conversation(created_project_id, "默认对话")
            st.session_state.project_id = created_project_id
            st.session_state.conversation_id = created_conversation_id
            clear_cached_reads()
            st.rerun()

    if len(projects) > 1 and st.button("删除当前项目", use_container_width=True):
        database.delete_project(project_id)
        st.session_state.project_id = None
        st.session_state.conversation_id = None
        clear_cached_reads()
        st.rerun()

    st.divider()
    st.subheader("对话")
    conversations = cached_conversations(project_id)
    if st.button("新建对话", use_container_width=True):
        st.session_state.conversation_id = database.create_conversation(project_id, "新对话")
        clear_cached_reads()
        st.rerun()

    for item in conversations:
        active = item["id"] == st.session_state.conversation_id
        label = f"{'● ' if active else ''}{item['title']}"
        if st.button(label, key=f"conversation_{item['id']}", use_container_width=True):
            if item["id"] != st.session_state.conversation_id:
                st.session_state.conversation_id = item["id"]
                clear_cached_reads()
                st.rerun()

    if st.session_state.conversation_id and len(conversations) > 1:
        if st.button("删除当前对话", use_container_width=True):
            database.delete_conversation(st.session_state.conversation_id)
            st.session_state.conversation_id = None
            clear_cached_reads()
            st.rerun()

project = next(item for item in cached_projects() if item["id"] == st.session_state.project_id)
messages = cached_messages(st.session_state.conversation_id)
listing_items = cached_listing(st.session_state.project_id)

chat_col, listing_col = st.columns([0.68, 0.32], gap="large")

with chat_col:
    st.header(project["name"])
    if project.get("description"):
        st.caption(project["description"])

    chat_box = st.container(height=620, border=False)
    with chat_box:
        if not messages:
            st.info("直接用自然语言开始。比如：把足金项链A加入上架清单，并说明需要补充哪些信息。")
        for message in messages:
            role = "assistant" if message["role"] == "assistant" else "user"
            with st.chat_message(role):
                st.markdown(message["content"])

    prompt = st.chat_input("输入消息，和 AI 讨论规则、商品、上架清单...")
    if prompt:
        with st.spinner("AI 正在处理..."):
            result = chat.handle_chat(st.session_state.project_id, st.session_state.conversation_id, prompt)
        st.session_state.conversation_id = st.session_state.conversation_id
        clear_cached_reads()
        st.rerun()

with listing_col:
    st.subheader("上架清单")
    st.caption("清单按项目隔离。你可以在聊天里让 AI 增减商品，也可以在这里删除。")

    if not listing_items:
        st.info("当前项目还没有上架商品。")
    for item in listing_items:
        with st.container(border=True):
            st.markdown(f"**{item['product_name']}**")
            st.caption(f"状态：{item['status']}")
            if item.get("notes"):
                st.write(item["notes"])
            if item.get("details"):
                with st.expander("结构化信息"):
                    st.json(item["details"])
            if st.button("移除", key=f"delete_listing_{item['id']}", use_container_width=True):
                database.delete_listing_item(item["id"])
                clear_cached_reads()
                st.rerun()

    with st.expander("项目数据"):
        st.write(f"项目 ID：{st.session_state.project_id}")
        st.write(f"对话 ID：{st.session_state.conversation_id}")
