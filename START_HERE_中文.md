# PluralForge AI v0.5 — 完整发布包使用说明

这是一个通用的多 Agent 协作决策研究原型。它允许不同模型独立提出候选方案、相互质疑、创造新方案并保留分歧。决策评分器不会让单个「元裁判」最终拍板。

**v0.5 新增 Information Value Learning Engine：** 通过外部核验的历史讨论/检索结果，学习「下一次只咨询某个 Agent、全体讨论或外部检索」在相同任务领域的经验增益及成本。样本不足时拒绝估计；历史回测使用信息可获得时间防止未来信息泄漏。它目前是经验预测，**不是因果 VoI 或强化学习**。

## 压缩包里有什么？

- `arbiter_plugin/`、`pluralforge/`：完整 Python 源码，保留旧导入路径兼容
- `dist/pluralforge_ai-0.5.0-py3-none-any.whl`：Python 安装包
- `examples/`：离线演示、历史学习示例，可选真实 API 示例
- `benchmarks/`：策略对照、时间序列学习评测（均为**合成数据**）
- `tests/`：自动化测试
- `docs/index.html`：无网络、无 API Key 可打开的交互网页
- `docs/preview.png`：网页效果图
- `docs/INFORMATION_VALUE_LEARNING.md`：学习算法与边界
- `docs/ARCHITECTURE.md`、`docs/BENCHMARK_PROTOCOL.md`：架构及评测方法
- `README.md`：英文 GitHub 首页说明

## Windows 11 安装

在项目目录打开 VS Code 终端：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m examples.value_learning_demo
python -m benchmarks.learning_temporal_replay
python -m pytest
```

没有 Python 源码安装需求时，也可以使用 Wheel：

```powershell
python -m pip install dist/pluralforge_ai-0.5.0-py3-none-any.whl
```

**网页演示：** 用浏览器打开 `docs/index.html`，其中的数据是脚本化模拟，不会连接你的数据库或调用付费 LLM。

**真实调用模型：** `python -m pip install -e ".[llm]"`，再按提供商设置自己的 API Key。不要把密钥加入 GitHub。

## 一个典型业务闭环

1. 外部宿主定义目标、约束、效用评价标准与预算。
2. 多个 Agent 独立提出方案。
3. 相互质疑、合成新方案、保留不同意见。
4. 判断是否还应额外咨询、检索或停止：有足够已核验历史记录时使用经验预测；否则使用明确的宿主先验或停止。
5. 独立评分，保留来源和风险提示，只输出建议。
6. 宿主获得可独立核验的结果后，记录同一评分标准下的执行前后质量、成本及证据可得时间。
7. 下一次决策只读取截至当前时间**已经可获得**的数据，继续学习。

## 重要限制

- 本项目没有证明多 Agent 辩论比单模型更准确；测试的结果不构成性能优越性证据。
- 历史数据存在行动选择偏差，不能自动证明因果收益，也不是自训练神经网络。
- `.whl` 是 Python 包，不是 Windows `.exe` 图形安装程序。
- API 服务用于本地开发，没有生产级鉴权。不要直接暴露到互联网。
- 新版 Wheel 已独立安装检查；真实付费模型 / MCP 客户端联调未在当前环境完成。
- 上传 GitHub 前确认没有自行添加的 `.env`、密钥、个人数据或私有文件。
