# AFH TypeScript SDK

独立 TypeScript SDK，封装 `rag-design` 版本的前端兼容 API。

## 使用

```ts
import { AFHClient } from "@afh-competition/sdk";

const client = new AFHClient({
  baseUrl: "http://127.0.0.1:8000",
});

const task = await client.createTask("default");

await client.streamChat(
  {
    task_id: task.task_id,
    message: "推荐我上架什么商品",
    knowledge_ids: [],
  },
  {
    onText: console.log,
    onEvent: (event) => {
      if (event.type === "risks") console.log("风险提示", event.items);
    },
  },
);
```

## 覆盖接口

- 项目：`listProjects`、`createProject`、`renameProject`
- 任务/历史：`createTask`、`listHistory`、`getHistoryDetail`
- 对话：`streamChat`
- 商品库：`listProducts`、`addProduct`、`deleteProduct`
- 知识库：`listOfficialKnowledge`、`listPersonalKnowledge`、`uploadKnowledge`、`deleteKnowledge`
- 汇总：`summarizeTask`、`summarizeProject`
- 健康检查：`health`、`llmHealth`

`ChatMetadata.risk_control` 会暴露后端风控审计结果，包括 `findings`、`should_block_actions` 和 `high_count`。
