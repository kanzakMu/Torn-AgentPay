# Tron-first 链上链下完整开发文档

## 1. 文档目标

这份文档用于指导 `AimiPay Tron` 从 0 开发，不继承旧仓库的历史兼容包袱，直接围绕以下目标构建：

- `Tron-first`
- `USDT-TRC20-first`
- `agent-native commerce`
- `buyer / seller / gateway / settlement` 端到端闭环
- 默认只做一条主线，不提前做多链抽象

这份文档不是“怎么修旧项目”，而是“新主仓库应该如何被正确地建出来”。

---

## 2. 产品定义

### 2.1 一句话定义

我们要做的是：

- 面向 AI agents、API、MCP 工具和 SaaS 的 `Tron-first programmable payment infrastructure`

### 2.2 解决的问题

当前 AI 服务交易存在几个结构性问题：

- AI agents 发现服务后，缺少标准化支付入口
- 小额高频、跨境、自动调用场景不适合传统支付流程
- API/MCP/SaaS 的按调用收费，缺少机器可发现、可验证、可结算的统一协议
- 商户侧接入复杂，买方侧自动化支付路径不稳定

### 2.3 我们的默认产品主线

- 默认链：`Tron`
- 默认资产：`USDT-TRC20`
- 默认买方：`AI buyer agent`
- 默认卖方：`API / MCP / SaaS service`
- 默认支付模型：`预存资金 -> 请求绑定凭证 -> 成功后结算`

---

## 3. 从 Skyfire 借鉴什么

在设计新仓库时，重点参考了 Skyfire 开发者文档中的几个有效模式：

- Skyfire Developer Docs: [Getting Started](https://docs.skyfire.xyz/docs/getting-started)
- Skyfire Developer Docs: [Service Discovery](https://docs.skyfire.xyz/docs/service-discovery)
- Skyfire Developer Docs: [Seller Onboarding](https://docs.skyfire.xyz/docs/seller-onboarding)
- Skyfire Developer Docs: [Skyfire Setup](https://docs.skyfire.xyz/docs/skyfire-setup)

### 3.1 要借鉴的优点

#### A. 服务发现优先

Skyfire 的核心优点不是“支付按钮”，而是：

- 先有 service directory / service metadata
- 再有 buyer 自动发现
- 再有 token/payment 执行

我们要保留这个思想：

- 任何 seller 服务都必须先可发现
- discovery 是协议的一等公民，不是附属文档

#### B. Seller Service 是明确对象

Skyfire 把 seller service 定义得很清楚：

- 服务名称
- 描述
- 服务类型
- 集成 URL
- 定价
- identity requirements

我们也应该有明确的 seller service 对象，而不是只暴露若干散乱 API。

#### C. 买卖双方的角色边界清晰

Skyfire 很强调：

- Buyer 负责发现、购买、携带支付凭证
- Seller 负责验凭证、交付服务、记录收费

这是正确的边界。新仓库必须坚持：

- Buyer 不负责 seller 的计费状态机
- Seller 不负责 buyer 的钱包状态

#### D. 集成面向 API / MCP / Website

Skyfire 明确支持：

- API
- MCP Server
- Website

这点非常重要，说明我们的发现协议和 seller gateway 也不能只面向单一接口形态。

### 3.2 不直接照搬的地方

我们不照搬 Skyfire 的几个部分：

- 不采用托管钱包作为系统前提
- 不把平台审批流程做成核心依赖
- 不把“平台 charge API”作为唯一结算方式
- 不依赖中心化 token issuance 作为基础支付模型

我们的区别是：

- 使用 `Tron + USDT-TRC20`
- 使用自托管或半托管 buyer/seller 执行器
- 使用链上支付通道作为结算基础
- discovery 保持开放协议，而不是只存在于封闭平台目录

---

## 4. 必须避免的旧错误

新仓库必须显式避免旧项目里已经证明代价很高的错误。

### 4.1 不要提前做多链主线

错误做法：

- 一开始就同时推进 Sol 和 Tron
- 抽象层先于产品主线成熟

正确做法：

- 只做 `Tron-first`
- 直到 Tron 闭环稳定前，不引入新的主链实现

### 4.2 不要让工具链复杂度压倒产品

错误做法：

- 过早把大量时间花在链工具链兼容、脚本层和历史部署路径上

正确做法：

- 先固定主链和工具链
- 优先保证产品闭环
- 部署复杂度必须服务产品，不得反客为主

### 4.3 不要让默认链是隐式的

错误做法：

- 表面支持多链，实际大量默认值仍然写死旧链

正确做法：

- 所有 discovery、CLI、配置、README、examples 都明确写 `Tron`

### 4.4 不要过早泛化钱包抽象

错误做法：

- 在还没有产品闭环之前就设计复杂钱包层

正确做法：

- 先以最小 buyer/seller 执行路径为核心
- 钱包先服务具体交易流程，再抽象

### 4.5 不要让协议和产品模型耦合混乱

错误做法：

- 把链上字段、服务发现、计费模型、商户展示逻辑混写

正确做法：

- 合约层只关心状态和资金
- discovery 只关心对外描述
- gateway 只关心接入和控制面
- settlement 只关心执行与恢复

### 4.6 不要让测试策略失控

错误做法：

- 大量重复跑重测试
- 同时验证太多维度

正确做法：

- 单元测试验证协议
- 集成测试验证 buyer/seller/gateway
- 一条最小端到端联调链路作为验收

---

## 5. 新仓库的边界

### 5.1 仓库范围

这个仓库只做以下内容：

- Tron 链上合约
- Tron 执行脚本
- Python buyer/seller/shared 应用层
- seller gateway
- discovery 协议
- settlement 执行与恢复
- 本地到 Nile 的部署与联调

### 5.2 不在当前仓库范围内

- Solana 主线开发
- 旧仓库兼容层
- 多链统一抽象平台
- 中心化平台审批系统
- 复杂风控系统

---

## 6. 推荐目录结构

```text
aimicropay-tron/
  contracts/
    AimiMicropayChannel.sol
    MockUSDT6.sol

  scripts/
    deploy_channel.js
    deploy_mock_usdt.js
    open_channel_exec.js
    claim_payment_exec.js
    close_channel_exec.js
    cancel_channel_exec.js
    protocol.js
    io.js

  test/
    AimiMicropayChannel.js

  python/
    buyer/
      wallet.py
      provisioner.py
      client.py
    seller/
      gateway.py
      settlement.py
      worker.py
    shared/
      discovery.py
      payments.py
      errors.py
      models.py

  examples/
    merchant_config.json
    open_channel_plan.json
    claim_payment_plan.json
    cancel_channel_plan.json

  spec/
    TRON_FIRST_DEVELOPMENT_GUIDE.md
    discovery.md
    settlement.md
    payment-channel.md

  README.md
  package.json
  hardhat.config.js
  .env.example
  .gitignore
```

---

## 7. 链上架构

### 7.1 核心合约

当前链上核心是：

- `AimiMicropayChannel.sol`
- `MockUSDT6.sol`

### 7.2 Payment Channel 状态

每个通道最少包含：

- `buyer`
- `seller`
- `token`
- `totalDeposit`
- `nonce`
- `expiresAt`
- `isActive`

### 7.3 核心动作

必须先稳定这 4 个动作：

1. `initializeChannel`
2. `claimPayment`
3. `closeChannel`
4. `cancelChannel`

不要在这一阶段提前加：

- top-up
- renew
- dispute/challenge
- partial claim batches
- advanced routing

### 7.4 链上设计原则

- 资金只用 `USDT-TRC20`
- 合约只处理资金和状态
- 请求绑定凭证必须保留
- `claim` 是以 buyer 签名凭证为授权依据
- `cancel` 必须 buyer + seller 双签
- `close` 必须过期后由 buyer 执行

### 7.5 合约阶段目标

阶段 1 只要做到：

- 通道可开
- 凭证可 claim
- 过期可 close
- 双签可 cancel
- Hardhat 测试全绿

---

## 8. 链下架构

### 8.1 Buyer 侧

Buyer 侧只保留最必要模块：

- `wallet.py`
  - 负责 buyer 私钥、地址、签名
- `provisioner.py`
  - 调用 `open_channel_exec.js`
- `client.py`
  - 调用 discovery
  - 确保有可用通道
  - 为每次请求生成支付凭证

Buyer 侧当前阶段不做复杂抽象：

- 不做多链 wallet framework
- 不做插件系统
- 不做过早的 SDK 大而全封装

### 8.2 Seller 侧

Seller 侧只保留：

- `gateway.py`
  - 暴露 paid routes
  - discovery / well-known
  - payment status / events / management API
- `settlement.py`
  - 把 seller ledger 中待结算记录转换为链上 claim 执行
- `worker.py`
  - 后台恢复、重试、异步 settlement

### 8.3 Shared 层

Shared 层只放链无关对象：

- `discovery.py`
- `payments.py`
- `errors.py`
- `models.py`

这些对象不允许包含：

- Solana 专有字段
- 历史兼容分支
- 链工具链路径

---

## 9. Discovery 设计

### 9.1 设计原则

Discovery 是产品主线，不是附加功能。

必须满足：

- 机器可读
- 面向 agent
- 面向 seller service
- 明确链、资产、价格、支付方式

### 9.2 必须包含的字段

建议最小 manifest：

```json
{
  "version": "v1",
  "kind": "aimipay-merchant",
  "transport": "http+aimipay",
  "primary_chain": {
    "chain": "tron",
    "channel_scheme": "tron-contract",
    "network": "nile",
    "seller_address": "T...",
    "contract_address": "T...",
    "asset_address": "T...",
    "asset_symbol": "USDT",
    "asset_decimals": 6
  },
  "routes": [],
  "plans": [],
  "endpoints": {
    "discover": "/.well-known/aimipay.json",
    "open_channel": "/_aimipay/channels/open",
    "payment_status_template": "/_aimipay/payments/{payment_id}"
  }
}
```

### 9.3 借鉴 Skyfire 的点

要借鉴 Skyfire 对 seller service metadata 的强调：

- 服务名
- 服务描述
- 定价模型
- 服务入口
- identity requirements

### 9.4 我们自己的增强点

必须额外包含：

- 链信息
- 通道合约地址
- 资产信息
- 请求绑定支付语义
- open/payment status/settlement 入口

---

## 10. 计费与支付模型

### 10.1 当前默认模型

默认做两类：

- `pay-per-use`
- `subscription metadata`

但链上第一阶段只强制实现：

- `pay-per-use`

订阅先体现在 discovery 和商户计划模型里，不急着把完整订阅状态机写上链。

### 10.2 请求绑定凭证

每次 paid request 需要绑定：

- HTTP method
- path
- body hash
- request deadline

这样可以避免：

- 凭证被横向复用
- seller claim 非目标请求
- 凭证脱离具体服务语义

#### 10.2.1 `request_deadline` 的执行语义

`request_deadline` 不是纯元数据，默认语义是“超过该时间后，这次请求授权不得再被结算”。

因此必须在三层同时执行：

- gateway 创建 payment 时拒绝已过期请求
- settlement 执行前再次拒绝已过期请求
- 合约 `claimPayment` 在链上拒绝超过 `request_deadline` 的 voucher

#### 10.2.2 voucher 金额语义

第一阶段 `claimPayment` 采用单次终局结算模型：

- voucher 中的 `amount` 表示本次通道的最终结算额
- 不是“在上一次基础上的增量金额”
- claim 成功后通道关闭，剩余资金按退款逻辑返还 buyer

这个语义必须在 SDK、脚本和文档中保持一致，避免业务方误按累计领取模型接入。

### 10.3 Payment 状态模型

链下应保留明确 payment 对象：

- `payment_id`
- `idempotency_key`
- `status`
- `route`
- `amount`
- `request_digest`
- `chain`
- `tx_id`
- `error`

---

## 11. Seller Gateway 设计

### 11.1 Gateway 职责

Gateway 负责：

- 暴露服务
- 输出 discovery
- 校验 buyer 提交的支付凭证
- 写 payment/event
- 将成功请求加入 settlement 队列

Gateway 不负责：

- 直接持有 buyer 钱包
- 直接编写复杂链逻辑
- 直接耦合到特定前端框架

### 11.2 Gateway 必须提供的接口

- `/.well-known/aimipay.json`
- `/_aimipay/discover`
- `/_aimipay/channels/open`
- `/_aimipay/payments/{payment_id}`
- `/_aimipay/events`
- `/_aimipay/settlements/execute`

#### 11.2.1 `open_channel` 的对外语义

`/_aimipay/channels/open` 当前定位为“开户参数协商与链上派生信息返回接口”，不是链上状态查询接口。

它应返回：

- 建议的 `deposit_atomic` 与 `expires_at`
- seller / contract / token 等链上参数
- 若可安全派生，则返回按合约同算法计算的 `channel_id`
- `channel_id_source`，明确标识该值是否来自链同源派生

它不应让调用方误解为：

- 通道已经在链上创建
- 返回的 `channel_id` 已代表某个真实 active channel 状态

### 11.3 默认 seller 接入目标

商户最小接入应是：

```python
app = FastAPI()
install_merchant_gateway(
    app,
    chain="tron",
    token="USDT-TRC20",
    contract_address="...",
    routes=[...]
)
```

---

## 12. Settlement 设计

### 12.1 目标

Settlement 是 seller 端的核心能力：

- 将服务交付后累积的可结算支付，批量转为链上 `claimPayment`

### 12.2 组件拆分

- `SettlementBatchSource`
  - 提供待结算记录
- `SettlementExecutor`
  - 调用 Tron claim 脚本
- `SettlementStore`
  - 记录 pending / submitted / success / failed
- `Worker`
  - 周期执行和恢复

### 12.3 当前阶段原则

- 只做最小可靠执行
- 重试必须幂等
- 失败必须可恢复
- 先不做复杂队列系统

---

## 13. 测试策略

### 13.1 测试分层

必须分成 4 层：

#### 第一层：合约单元测试

- `initialize`
- `claim`
- `close`
- `cancel`

#### 第二层：脚本测试

- deploy script
- open/claim/cancel script plan parsing
- digest/signature correctness

#### 第三层：Python 集成测试

- gateway discovery
- buyer 自动发现
- seller settlement 编排
- payment status / event model

#### 第四层：最小端到端联调

- seller 启动
- buyer 发现服务
- buyer open
- buyer 请求付费接口
- seller 记账
- seller claim

### 13.2 必须避免的测试错误

- 不要为拿日志反复盲跑整套测试
- 不要让同一件事在多层重复验证
- 不要先写大量回归再定义主线

---

## 14. 本地开发顺序

### Phase 0: 建仓

- 建立新仓库
- 放入已验证的 Tron 合约和脚本
- 固定 README、目录、规范

### Phase 1: 链上稳定

- 合约
- Hardhat
- 执行脚本
- plan 文件

完成标准：

- `npm install`
- `npm run build`
- `npm test`

### Phase 2: Discovery 与 Gateway

- seller service metadata
- `.well-known`
- paid route middleware
- payment status

### Phase 3: Buyer

- buyer wallet
- buyer provisioner
- buyer client
- request-bound voucher generation

### Phase 4: Settlement

- seller settlement executor
- settlement worker
- retry / event / audit

### Phase 5: 本地闭环

- buyer/seller/gateway 全链路
- mock usdt
- 一条 paid route 跑通

### Phase 6: Nile

- deploy mock
- deploy channel
- open/claim/cancel
- seller gateway 对真实 Nile RPC 执行

---

## 15. 第一周开发计划

### Day 1

- 固定仓库结构
- 固定 README
- 固定合约与脚本

### Day 2

- 写 `spec/discovery.md`
- seller gateway 最小版

### Day 3

- buyer wallet + provisioner 最小版
- open channel 本地打通

### Day 4

- 请求绑定凭证
- paid route 验证
- payment status

### Day 5

- seller settlement executor
- settlement worker

### Day 6

- 本地端到端联调
- 清理错误模型和日志

### Day 7

- 补 README/examples
- 准备 Nile 验证

---

## 16. 成功标准

新仓库阶段 1 成功，不以“代码量”衡量，而以以下标准衡量：

- 新开发者 10 分钟内读懂仓库主线
- seller 可通过一份配置启动 gateway
- buyer 可自动发现 seller
- buyer 可开通 Tron 通道
- paid route 可收取 payment voucher
- seller 可执行 claim
- local end-to-end 至少 1 条链路稳定通过

---

## 17. 当前行动要求

从现在开始：

- 不再围绕旧仓库做大规模兼容重构
- 不再把 Sol 作为当前主干设计输入
- 所有新增代码都默认属于新仓库
- 所有文档、测试、示例都以 `Tron-first` 为默认前提

这就是新的主线。

---

## 18. 新的产品架构图

### 18.1 颗粒度重新对齐

当前产品目标不应再被定义成“支付通道协议”或“商家收款 SDK”。

新的统一定义是：

- 我们要做的是 `agent-native automatic procurement and payment infrastructure`

更具体地说：

- 用户或开发者安装我们的程序 / runtime / skill
- AI agent 自动创建或连接钱包
- AI agent 在执行任务时发现自己需要外部资源
- AI agent 自动发现商家或其他 agent 的付费接口
- AI agent 自动估算完成任务所需成本
- AI agent 自动完成支付、获取资源、继续完成任务

默认目标场景包括：

- AI 联网检索时按次购买搜索 / 数据接口
- AI 写代码时调用第三方代码审查 / 测试 / 部署 API
- AI 自有额度不足时自动采购外部额度
- agent 与商家、agent 与 agent 的机器对机器交易

### 18.2 新的产品分层

从现在起，主架构按 6 层理解：

1. `Agent Runtime Layer`
   - 安装到 AI agent 侧的 runtime / skill
   - 负责钱包、发现、预算、采购、结果回注

2. `Capability Discovery Layer`
   - 发现商家或其他 agent 的能力
   - 暴露价格、计费方式、交付方式、支付方式

3. `Budget & Decision Layer`
   - 估算任务完成成本
   - 做供应方选择与预算决策
   - 决定是否购买、买多少、买哪家

4. `Payment Orchestration Layer`
   - 开通通道
   - 生成授权
   - 创建 payment
   - 触发 settlement
   - 查询 payment 状态

5. `Settlement & Execution Layer`
   - 把链下 payment 转成链上 claim
   - 做重试、恢复、异步执行

6. `Merchant / Agent Capability Layer`
   - 商家或其他 agent 发布可售能力
   - 对外提供 API / MCP / SaaS / tool route

### 18.3 新的总体架构图

```text
+---------------------------------------------------------------+
|                    Agent Runtime / Skill                      |
|---------------------------------------------------------------|
| Wallet | Vendor Discovery | Budget Estimator | Purchase Brain |
+-------------------------+---------------------+---------------+
                          | discover / compare / decide
                          v
+---------------------------------------------------------------+
|              Capability Discovery / Merchant Metadata         |
|---------------------------------------------------------------|
| well-known manifest | routes | plans | pricing | chain info   |
+-------------------------+---------------------+---------------+
                          | choose route / plan
                          v
+---------------------------------------------------------------+
|                 Buyer Payment Orchestration                   |
|---------------------------------------------------------------|
| open channel | build auth | create payment | execute payment  |
+-------------------------+---------------------+---------------+
                          | payment / settlement control plane
                          v
+---------------------------------------------------------------+
|                 Seller Gateway / Settlement                   |
|---------------------------------------------------------------|
| discovery | payment intake | auth checks | queue | claim exec |
+-------------------------+---------------------+---------------+
                          | claimPayment / close / cancel
                          v
+---------------------------------------------------------------+
|                 Tron Contract + USDT-TRC20                    |
|---------------------------------------------------------------|
| channel state | funds escrow | voucher authorization          |
+---------------------------------------------------------------+
```

### 18.4 安装后的目标体验

买方 / agent 侧理想体验：

```python
runtime = install_agent_payments(...)
runtime.enable_auto_wallet()
runtime.enable_vendor_discovery()
runtime.enable_budget_estimation()
runtime.enable_auto_purchase()
```

商家 / 能力提供方理想体验：

```python
merchant = install_sellable_capability(...)
merchant.publish_api(...)
merchant.publish_mcp_tool(...)
merchant.publish_usage_route(...)
```

注意：

- 当前代码还没有完全实现上面这组高层 API
- 但后续所有设计都应朝这个抽象收敛

### 18.5 与当前实现的映射

当前仓库里已经可复用的基础能力：

- `buyer/client.py`
  - 已接近 buyer 采购客户端
- `buyer/wallet.py`
  - 已接近 agent 自动钱包入口
- `seller/gateway.py`
  - 已接近商家能力发布与控制面
- `seller/settlement.py`
  - 已接近 seller 执行与恢复内核
- `shared/discovery.py`
  - 已接近能力发现协议层
- `scripts/claim_payment_exec.js` / `local_smoke_pipeline.js`
  - 已接近真实执行后端

当前仍未形成独立模块的能力：

- 任务成本估算器
- 多供应方比较与选择器
- 高层自动采购 runtime
- 安装型 skill / SDK 外壳
- 交付结果回注到 agent 执行链路

---

## 19. 下一阶段开发顺序

### 19.1 阶段目标

从现在开始，下一阶段不再把“再补若干支付接口”作为主线。

新的阶段目标是：

- 让 agent 安装后真正具备 `发现 -> 预算 -> 购买 -> 调用 -> 继续执行任务` 的能力

### 19.2 下一阶段的正确顺序

#### Phase A: 固化能力发现模型

目标：

- 把当前 seller manifest 从“支付元数据”升级成“能力市场元数据”

必须补充的字段：

- capability type
- usage unit
- pricing model
- settlement backend
- auth requirements
- response contract / delivery mode
- budget hints

完成标准：

- buyer 不只是发现 route
- buyer 能理解“我买到的是什么能力”

#### Phase B: 建立预算与决策层

目标：

- 在 buyer / runtime 侧引入任务成本估算

至少要支持：

- 单 route 成本估算
- 任务预算上限
- 是否值得购买的决策
- 供应方选择基础规则

建议新增对象：

- `CapabilityOffer`
- `TaskBudget`
- `PurchaseDecision`
- `BudgetEstimator`

完成标准：

- AI 不再只会“发现后直接付款”
- 而是先做预算判断

#### Phase C: 抽出高层自动采购接口

目标：

- 把当前 `ensure_channel_for_route / create_payment / execute_payment` 收敛成面向 agent 的高层动作

建议新增接口：

- `buy_capability(...)`
- `pay_for_task(...)`
- `purchase_route(...)`

建议目标形态：

```python
result = runtime.buy_capability(
    capability="web_search",
    budget_atomic=500000,
    task_context="need 10 external searches for coding task",
)
```

完成标准：

- agent 调的是高层采购动作
- 而不是手工串 buyer client 的多个低层 API

#### Phase D: 前置授权校验与交付状态机

目标：

- 把当前 `create payment -> execute settlement` 两段式流程，升级为：
  `authorize -> fulfill -> settle`

必须新增的控制点：

- seller 前置验签
- seller 前置验通道
- seller 前置验 nonce
- 服务交付完成后再进入 settlement

完成标准：

- payment 记录不再只是待结算条目
- 而是成为真正的交易状态机

#### Phase E: 低代码安装层

目标：

- 做出 buyer / seller 两侧真正的低代码安装体验

买方侧目标：

- `install_agent_payments(...)`
- `enable_auto_wallet()`
- `enable_auto_purchase()`

卖方侧目标：

- `install_sellable_capability(...)`
- `publish_usage_route(...)`
- `publish_mcp_tool(...)`

完成标准：

- 新用户不需要理解 settlement / provisioner / gateway 细节
- 通过 1-2 段配置即可接入

#### Phase F: 供应方市场与多商家选择

目标：

- 支持 buyer 面向多个 seller / agent 做发现和选择

至少要支持：

- 多供应方发现
- 价格比较
- 能力比较
- 成功率 / 延迟等策略选择

完成标准：

- 系统从“单商家支付 SDK”升级为“agent 采购网络入口”

### 19.3 暂不优先的事项

下一阶段不优先做：

- 多链抽象平台
- 复杂争议机制
- 超前治理 / 风控大系统
- 大型前端 dashboard
- 中心化审批平台

理由：

- 这些都不能直接帮助 agent 获得“自动发现与自动采购”能力

### 19.4 建议的实际开发顺序

如果按两周到三周的现实开发节奏，建议顺序是：

1. 扩展 discovery / manifest 的 capability 字段
2. 定义 `CapabilityOffer / TaskBudget / PurchaseDecision`
3. 做 buyer 侧 `buy_capability()` 高层接口
4. 做 seller 侧 `authorize -> fulfill -> settle` 状态机
5. 做 buyer / seller 的安装型 runtime API
6. 做多供应方 discovery 与 vendor selection
7. 最后再进入 Nile / 真测试网验证

### 19.5 新的阶段成功标准

下一阶段是否成功，不看代码量，看下面 6 条：

- agent 安装后可自动创建或连接钱包
- agent 可自动发现至少 2 个能力提供方
- agent 可估算一项任务的大致采购成本
- agent 可自动完成一次 paid capability 调用
- seller 可在交付完成后再推进 settlement
- buyer/seller 至少有 1 条“自动采购”端到端链路稳定通过
