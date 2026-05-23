from __future__ import annotations

from typing import Any

import streamlit as st

from agent import chat, database
from agent.llm import model_status


st.set_page_config(page_title="执行辅助 Agent", layout="wide")
database.init_db()


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
        ["项目工作台", "商品管理"],
        index=0 if st.session_state.page == "workspace" else 1,
        label_visibility="collapsed",
    )
    new_page = "workspace" if nav_choice == "项目工作台" else "products"
    if new_page != st.session_state.page:
        st.session_state.page = new_page
        st.rerun()

if st.session_state.page == "products":
    st.header("商品管理")
    st.caption("统一维护所有商品信息。商品编号自动生成，无需手动填写。")

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
                    "商品编号": item["product_code"],
                    "商品名称": item["name"],
                    "品类": item["category"],
                    "品牌": item["brand"],
                    "SKU": item["sku"],
                    "价格": item["price"],
                    "库存": item["stock"],
                    "状态": item["status"],
                }
                for item in products
            ]
            st.dataframe(table_rows, use_container_width=True, hide_index=True)

            product_options = {f"{item['product_code']} - {item['name']}": item["id"] for item in products}
            selected_product = st.selectbox("选择要编辑的商品", [""] + list(product_options.keys()))
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
            st.caption(f"正在编辑：{editing_product['product_code']}")
        else:
            st.caption("新增商品时自动生成商品编号")

        with st.form("product_form", clear_on_submit=False):
            name = st.text_input("商品名称", value=(editing_product or {}).get("name", ""))
            category = st.text_input("品类", value=(editing_product or {}).get("category", ""))
            brand = st.text_input("品牌", value=(editing_product or {}).get("brand", ""))
            sku = st.text_input("SKU", value=(editing_product or {}).get("sku", ""))
            col_a, col_b = st.columns(2)
            with col_a:
                price = st.number_input("价格", min_value=0.0, value=float((editing_product or {}).get("price", 0) or 0), step=1.0)
                stock = st.number_input("库存", min_value=0, value=int((editing_product or {}).get("stock", 0) or 0), step=1)
            with col_b:
                sales_30d = st.number_input("近30天销量", min_value=0, value=int((editing_product or {}).get("sales_30d", 0) or 0), step=1)
                rating = st.number_input("好评率(%)", min_value=0.0, max_value=100.0, value=float((editing_product or {}).get("rating", 0) or 0), step=0.1)
            status_value = (editing_product or {}).get("status", "在售")
            statuses = ["在售", "待上架", "已下架", "缺货", "待确认"]
            status_index = statuses.index(status_value) if status_value in statuses else 0
            status = st.selectbox("状态", statuses, index=status_index)
            notes = st.text_area("备注", value=(editing_product or {}).get("notes", ""), height=100)
            submitted = st.form_submit_button("保存商品", type="primary", use_container_width=True)

        payload = {
            "name": name,
            "category": category,
            "brand": brand,
            "sku": sku,
            "price": price,
            "stock": stock,
            "sales_30d": sales_30d,
            "rating": rating,
            "status": status,
            "notes": notes,
        }
        if submitted:
            if not name.strip():
                st.warning("商品名称不能为空。")
            elif editing_product:
                database.update_catalog_product(editing_product["id"], payload)
                st.success("商品已更新。")
                st.rerun()
            else:
                product_id = database.create_catalog_product(payload)
                st.session_state.editing_product_id = product_id
                st.success("商品已创建。")
                st.rerun()

        if editing_product:
            c1, c2 = st.columns(2)
            if c1.button("新建空白商品", use_container_width=True):
                st.session_state.editing_product_id = None
                st.rerun()
            if c2.button("删除商品", use_container_width=True):
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
