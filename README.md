# 工业设备售后服务风险预测系统

基于工单数据的多维度风险预测与异常检测机器学习系统。

## 项目概述

工业设备售后服务场景中，工单的成本超支、服务超时、退回/作废等问题直接影响运营效率。本项目从178,609条历史工单数据出发，构建了完整的风控ML流水线：

- **监督学习**：预测工单是否属于高风险（成本/时长/退回/低效）
- **无监督学习**：Isolation Forest 异常检测，发现不符合常规模式的异常工单
- **可解释性**：SHAP 分析揭示风险驱动因素

## 快速开始

```bash
# 1. 安装依赖
pip install numpy pandas scikit-learn xgboost lightgbm shap matplotlib seaborn joblib

# 2. 准备数据
# 将数据文件 000000_0.csv 放到当前目录下

# 3. 运行完整流水线
python risk_prediction.py

# 4. 对新数据预测
python risk_prediction.py --predict new_data.csv --model XGBoost
```

## 模型性能

| 模型 | AUC | 召回率 | 最优阈值 |
|------|:---:|:-----:|:--------:|
| **XGBoost** 🥇 | **0.708** | 64.3% | 0.472 |
| Random Forest | 0.703 | 62.1% | 0.476 |
| LightGBM | 0.671 | 56.4% | 0.183 |
| Logistic Regression | 0.670 | 57.8% | 0.490 |

## 风险定义

风险从4个维度综合评估：

| 维度 | 权重 | 指标 |
|------|:---:|------|
| 成本风险 | 30% | 工单差旅费（前15%） |
| 时长风险 | 25% | 服务总时长（前15%） |
| 退回风险 | 25% | 退回+作废占比（前15%） |
| 低效风险 | 20% | 人均服务时长（前15%） |

## 特征工程（44个特征）

- **14个原始预测器**：工单规模、人数、设备数、工单类型等
- **4个衍生特征**：设备总数、服务范围广度、收费占比、人均设备
- **14个油站聚合特征**：按油站历史均值聚合
- **12个对数变换**：拉平长尾分布

> ⚠️ **防数据泄露**：风险标签定义使用的结果变量（差旅费、服务时长、退回率等）及其衍生特征**不会进入模型输入**。

## 项目结构

```
05_ML/
├── risk_prediction.py          # 主流水线脚本（~1260行）
├── fengxian.py                 # 快捷入口
├── risk_output/                # 输出目录
│   ├── models/                 # 训练好的模型 (.pkl)
│   ├── roc_curves.png          # ROC曲线对比
│   ├── pr_curves.png           # PR曲线对比
│   ├── confusion_matrix.png    # 混淆矩阵
│   ├── shap_importance_XGBoost.png  # SHAP特征重要性
│   ├── shap_beeswarm_XGBoost.png    # SHAP蜂群图
│   ├── shap_dependence_XGBoost.png  # SHAP依赖图
│   ├── anomaly_analysis.png    # 异常检测分析
│   ├── eda_distributions.png   # 风险指标分布
│   ├── eda_correlation.png     # 特征相关性
│   ├── eda_high_vs_low.png     # 高风险vs低风险对比
│   ├── eda_missing.png         # 缺失值分布
│   └── model_comparison.csv    # 模型对比表
└── README.md
```

## 输出图表预览

运行 `risk_prediction.py` 后，所有图表输出到 `risk_output/` 目录，标题均为中英双语。

## License

MIT
