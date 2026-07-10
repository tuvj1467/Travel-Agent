# 旅行规划助手 - 项目架构说明

## 项目概述

基于 LangGraph 的智能旅行规划助手，通过对话收集用户需求，使用多节点协作生成预算感知的旅行方案。系统采用结构化状态管理，支持条件分支和循环调整，确保行程在预算约束内生成。

## 整体架构

### 当前结构

```
Travel/
├── agent                    #agent节点配置和图的构建 ✅
├── config                   # 配置文件 ✅
├── models                   # 数据模型（已优化为结构化） ✅
├── tools                    # 外部工具函数（待实现） ✅
├── utils                    # 公共工具（待实现） ✅
├── main.py                  # 主程序入口 ✅
├── chat_consultant.py       # 对话顾问（需求收集） ✅
├── requirements.txt         # 依赖管理 ✅
├── .env                     # 环境变量 ✅
├── .env.example             # 环境变量模板 ✅
├── ARCHITECTURE.md          # 架构说明（本文件） ✅
└── README.md                # 项目说明 ✅
```

