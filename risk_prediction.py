"""
工业设备售后服务风险预测系统
===========================
基于工单数据的多维度风险预测与异常检测

工作流程:
  1. 数据加载与清洗（处理 userids 字段逗号导致的列数不一致）
  2. 探索性数据分析 (EDA) 与可视化
  3. 多维度风险标签构建（成本、效率、退回、综合）
  4. 特征工程（比率、交互、聚合特征）
  5. 多模型训练（XGBoost / LightGBM / Random Forest）
  6. 模型评估与对比（AUC、KS、召回率）
  7. SHAP 可解释性分析
  8. 异常检测（Isolation Forest + 角度定位）
  9. 新数据预测接口

Author: Auto-generated for risk prediction
Date: 2026-06-05
"""

import os
import sys
import warnings
import logging
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # 无 GUI 后端，兼容服务器环境
import matplotlib.pyplot as plt
import seaborn as sns

# 中文字体配置（解决标题显示为方框的问题）
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "WenQuanYi Micro Hei", "Noto Sans CJK"]
plt.rcParams["axes.unicode_minus"] = False  # 正常显示负号

from sklearn.model_selection import (
    train_test_split,
    StratifiedKFold,
    cross_val_score,
)
from sklearn.preprocessing import (
    StandardScaler,
    RobustScaler,
    LabelEncoder,
    QuantileTransformer,
)
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.metrics import (
    roc_auc_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_curve,
    precision_recall_curve,
    silhouette_score,
    average_precision_score,
    log_loss,
)
from sklearn.linear_model import LogisticRegression

import xgboost as xgb
import lightgbm as lgb
import shap

warnings.filterwarnings("ignore")

# =========================================================================
# 配置
# =========================================================================
DATA_PATH = Path(__file__).parent / "000000_0.csv"
OUTPUT_DIR = Path(__file__).parent / "risk_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 风险阈值分位数（前 top_pct 视为高风险）
RISK_TOP_PCT = 0.15  # 前 15% 为高风险
MODEL_SEED = 42
TEST_SIZE = 0.2
N_JOBS = -1

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(OUTPUT_DIR / "pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# =========================================================================
# 字段定义
# =========================================================================
COLUMNS = [
    "wo_id",                 # 工单id
    "callaccept_id",         # 来电受理单id
    "oil_station_id",        # 油站id
    "userids",               # 服务用户id（可忽略，逗号分隔列表）
    "wo_num",                # 工单单据数量
    "back_num",              # 退回工单数量
    "abolished_num",         # 作废工单数量
    "wait_dispatch_num",     # 待派工数量
    "wait_departure_num",    # 待出发数量
    "alread_complete_num",   # 已完工工单数量
    "processing_num",        # 正在处理工单数量
    "people_num",            # 工单人数
    "service_total_duration",     # 服务总时长（小时）
    "repair_response_duration",   # 报修响应时长（小时）
    "customer_repair_num",   # 客户报修工单数量
    "charg_num",             # 收费工单数量
    "repair_device_num",     # 维修设备数量
    "install_device_num",    # 安装设备数量
    "install_num",           # 安装单数量
    "repair_num",            # 维修单数量
    "remould_num",           # 改造单数量
    "inspection_num",        # 巡检单数量
    "workorder_trvl_exp",    # 工单差旅费
    "partition_date",        # 分区日期
]

# 数值特征列（不含 ID 和日期）
NUMERIC_COLS = [
    "wo_num", "back_num", "abolished_num", "wait_dispatch_num",
    "wait_departure_num", "alread_complete_num", "processing_num",
    "people_num", "service_total_duration", "repair_response_duration",
    "customer_repair_num", "charg_num", "repair_device_num",
    "install_device_num", "install_num", "repair_num", "remould_num",
    "inspection_num", "workorder_trvl_exp",
]

# 排除列（不参与建模的 ID 列）
ID_COLS = {"wo_id", "callaccept_id", "oil_station_id", "userids", "partition_date"}


# =========================================================================
# 第一步：数据加载
# =========================================================================
def load_data(filepath: Path) -> pd.DataFrame:
    """
    加载 CSV 数据，处理因 userids 逗号列表导致的列数不一致问题。

    策略: 每行固定取前 3 列 (wo_id, callaccept_id, oil_station_id)，
          再从尾部固定取 20 列 (userids 合并 + 19 个数值特征 + partition_date)，
          中间多余的字段都属于 userids 列表的一部分。
    """
    logger.info(f"正在加载数据: {filepath}")
    if not filepath.exists():
        raise FileNotFoundError(f"数据文件不存在: {filepath}")

    # 先读取所有行，分割字段
    raw_lines = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            raw_lines.append(parts)

    n_cols = [len(p) for p in raw_lines]
    logger.info(f"总行数: {len(raw_lines)}")
    logger.info(f"列数分布: min={min(n_cols)}, max={max(n_cols)}, "
                f"24列占比={sum(1 for c in n_cols if c==24)/len(n_cols)*100:.1f}%")

    # 鲁棒解析：每行固定取前3 + 后20，中间合并到 userids
    records = []
    n_errors = 0
    for parts in raw_lines:
        try:
            if len(parts) < 23:
                n_errors += 1
                continue

            # 前 3 个固定字段
            wo_id = parts[0]
            callaccept_id = parts[1]
            oil_station_id = parts[2]

            # 后 20 个字段（userids + 19 数值特征 + partition_date）
            tail = parts[-20:]

            # 中间的字段全部合并到 userids（若有）
            mid = parts[3:-20]
            userids_combined = ",".join(mid) if mid else tail[0]

            record = [wo_id, callaccept_id, oil_station_id, userids_combined] + tail
            records.append(record)
        except Exception as e:
            n_errors += 1
            continue

    df = pd.DataFrame(records, columns=COLUMNS)
    logger.info(f"成功解析: {len(df)} 行, 跳过: {n_errors} 行")

    # 数值列类型转换
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 日期统一处理
    df["partition_date"] = pd.to_datetime(
        df["partition_date"].astype(str).str[:8], format="%Y%m%d", errors="coerce"
    )

    logger.info(f"\n数据概览:\n{df[NUMERIC_COLS].describe().to_string()}")
    logger.info(f"\n缺失值统计:\n{df[NUMERIC_COLS].isnull().sum().to_string()}")
    return df


# =========================================================================
# 第二步：特征工程
# =========================================================================
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    从原始字段衍生丰富的特征集。
    """
    logger.info("开始特征工程...")
    feat = df.copy()

    # ---------- 1. 比率/占比特征 ----------
    # 退回率
    feat["back_ratio"] = feat["back_num"] / (feat["wo_num"] + 1e-6)
    # 作废率
    feat["abolished_ratio"] = feat["abolished_num"] / (feat["wo_num"] + 1e-6)
    # 完成率
    feat["complete_ratio"] = feat["alread_complete_num"] / (feat["wo_num"] + 1e-6)
    # 处理中占比
    feat["processing_ratio"] = feat["processing_num"] / (feat["wo_num"] + 1e-6)
    # 待派工占比
    feat["wait_dispatch_ratio"] = feat["wait_dispatch_num"] / (feat["wo_num"] + 1e-6)

    # 退回+作废占比（核心风险指标）
    feat["return_abolished_ratio"] = (
        feat["back_num"] + feat["abolished_num"]
    ) / (feat["wo_num"] + 1e-6)

    # ---------- 2. 人均指标 ----------
    feat["duration_per_person"] = feat["service_total_duration"] / (feat["people_num"] + 1e-6)
    feat["trvl_exp_per_person"] = feat["workorder_trvl_exp"] / (feat["people_num"] + 1e-6)
    feat["device_per_person"] = (
        feat["repair_device_num"] + feat["install_device_num"]
    ) / (feat["people_num"] + 1e-6)

    # ---------- 3. 服务密度/强度 ----------
    feat["device_density"] = (
        feat["repair_device_num"] + feat["install_device_num"]
    ) / (feat["service_total_duration"] + 1e-6)
    feat["cost_per_device"] = feat["workorder_trvl_exp"] / (
        feat["repair_device_num"] + feat["install_device_num"] + 1e-6
    )
    feat["cost_per_duration"] = feat["workorder_trvl_exp"] / (
        feat["service_total_duration"] + 1e-6
    )

    # ---------- 4. 工单类型复合特征 ----------
    feat["total_device_count"] = feat["repair_device_num"] + feat["install_device_num"]
    feat["service_scope"] = (
        feat["repair_num"].gt(0).astype(int)
        + feat["install_num"].gt(0).astype(int)
        + feat["remould_num"].gt(0).astype(int)
        + feat["inspection_num"].gt(0).astype(int)
    )

    # ---------- 5. 响应效率 ----------
    feat["response_efficiency"] = feat["repair_response_duration"] / (
        feat["service_total_duration"] + 1e-6
    )

    # ---------- 6. 收费占比 ----------
    feat["charg_ratio"] = feat["charg_num"] / (feat["customer_repair_num"] + 1e-6)

    # ---------- 7. 对数变换（处理长尾分布） ----------
    for col in NUMERIC_COLS:
        if col in feat.columns:
            feat[f"log_{col}"] = np.log1p(feat[col].clip(lower=0))

    logger.info(f"特征工程完成，当前特征数: {feat.shape[1]}")
    return feat


# =========================================================================
# 第二步B：油站聚合特征（无泄漏，仅用预测器）
# =========================================================================
def add_station_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    为每个油站计算历史聚合特征。

    仅使用"事前已知"的预测器特征，不使用结果变量，
    因此不会造成数据泄露。
    """
    logger.info("正在添加油站级别聚合特征...")
    result = df.copy()

    # 用于聚合的预测器特征（不含结果变量）
    agg_cols = [
        "wo_num", "people_num", "alread_complete_num",
        "customer_repair_num", "charg_num",
        "repair_device_num", "install_device_num",
        "install_num", "repair_num", "remould_num", "inspection_num",
        "total_device_count", "service_scope",
    ]
    agg_cols = [c for c in agg_cols if c in result.columns]

    if "oil_station_id" not in result.columns:
        logger.warning("缺少 oil_station_id，跳过油站特征")
        return result

    # 按油站分组计算均值
    station_stats = result.groupby("oil_station_id")[agg_cols].mean()
    station_stats.columns = [f"station_avg_{c}" for c in station_stats.columns]

    # 工单数量（该油站出现次数）
    station_counts = result["oil_station_id"].value_counts()
    station_orders = station_counts.to_frame("station_workorder_count")

    # 合并
    station_features = station_stats.join(station_orders)

    # 回填到原数据
    result = result.merge(
        station_features, left_on="oil_station_id",
        right_index=True, how="left",
    )

    logger.info(f"已添加 {len(station_features.columns)} 个油站聚合特征")
    return result


# =========================================================================
# 第三步：风险标签定义
# =========================================================================
def define_risk_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    从多个维度定义风险标签，最终生成综合风险评分。

    风险维度:
      1. 成本风险: 差旅费排前 RISK_TOP_PCT
      2. 时长风险: 服务总时长排前 RISK_TOP_PCT
      3. 退回风险: 退回/作废占比排前 RISK_TOP_PCT
      4. 低效风险: 人均时长排前 RISK_TOP_PCT
    """
    logger.info("正在构建多维度风险标签...")
    labels = df.copy()

    # ---------- 各维度风险评分 (0~1) ----------
    # 使用 rank 归一化到 [0, 1]（越大越危险）
    risk_dims = [
        "workorder_trvl_exp",
        "service_total_duration",
        "return_abolished_ratio",
        "duration_per_person",
    ]
    for col in risk_dims:
        series = labels[col].fillna(0).clip(lower=0)
        labels[f"risk_score_{col}"] = series.rank(pct=True)

    # ---------- 综合风险评分 ----------
    labels["risk_score_composite"] = (
        labels["risk_score_workorder_trvl_exp"] * 0.30       # 成本 30%
        + labels["risk_score_service_total_duration"] * 0.25  # 时长 25%
        + labels["risk_score_return_abolished_ratio"] * 0.25  # 退回 25%
        + labels["risk_score_duration_per_person"] * 0.20     # 低效 20%
    )

    # ---------- 二分类标签（前 N% 为高风险） ----------
    threshold = labels["risk_score_composite"].quantile(1 - RISK_TOP_PCT)
    labels["is_high_risk"] = (labels["risk_score_composite"] >= threshold).astype(int)

    # 各维度独立二分类标签
    # 对零膨胀特征（如 return_abolished_ratio），在非零子集中取分位数
    for col in risk_dims:
        score_col = f"risk_score_{col}"
        # 如果该维度存在大量零值，取非零值的分位数作为阈值，且至少 > 0
        nonzero = labels.loc[labels[col] > 0, score_col]
        if len(nonzero) > 100:
            th = nonzero.quantile(1 - RISK_TOP_PCT)
        else:
            th = labels[score_col].quantile(1 - RISK_TOP_PCT)
        # 至少要求 > 0，避免全零列导致全部标记为风险
        th = max(th, 1e-6)
        labels[f"is_high_risk_{col}"] = (
            labels[score_col] >= th
        ).astype(int)

    risk_rate = labels["is_high_risk"].mean()
    logger.info(f"高风险阈值 (composite >= {threshold:.4f}), "
                f"高风险占比: {risk_rate*100:.1f}%")
    logger.info(f"各维度高风险占比:")
    for col in risk_dims:
        logger.info(f"  {col}: {labels[f'is_high_risk_{col}'].mean()*100:.1f}%")

    return labels


# =========================================================================
# 第四步：数据预处理（训练用）
# =========================================================================
def prepare_training_data(
    df: pd.DataFrame, target_col: str = "is_high_risk"
) -> tuple:
    """
    准备训练数据：选择特征列、处理缺失值、标准化。

    关键设计：防止数据泄露！
    - 风险标签 is_high_risk 由 workorder_trvl_exp / service_total_duration /
      return_abolished_ratio / duration_per_person 定义
    - 这些"结果变量"及其衍生特征不能出现在模型输入中
    - 模型只能使用**事前已知**的特征来预测风险

    允许的预测特征（工单创建/派工时可获取）:
      - 工单规模: wo_num, people_num, 设备数量
      - 工单类型: 维修/安装/改造/巡检数量
      - 油站历史特征: 油站的历史工单规模均值
    """
    # 预测特征（事前已知，不包含结果变量）
    predictor_features = [
        # 工单规模
        "wo_num", "people_num",
        # 工单进度状态（派工前已知的派工信息）
        "alread_complete_num", "processing_num",
        "wait_dispatch_num", "wait_departure_num",
        # 设备与服务量
        "customer_repair_num", "charg_num",
        "repair_device_num", "install_device_num",
        # 工单类型
        "install_num", "repair_num", "remould_num", "inspection_num",
    ]

    # 安全的衍生特征（不依赖结果变量）
    derived_features = [
        "total_device_count", "service_scope",
        "charg_ratio", "device_per_person",
    ]

    # 油站层级聚合特征（仅使用预测器，不使用结果变量，故无泄漏）
    station_features = [c for c in df.columns if c.startswith("station_")]
    if not station_features:
        station_features = []

    # 安全的对数特征
    safe_log_features = [
        "log_wo_num", "log_people_num",
        "log_alread_complete_num", "log_processing_num",
        "log_customer_repair_num", "log_charg_num",
        "log_repair_device_num", "log_install_device_num",
        "log_install_num", "log_repair_num",
        "log_remould_num", "log_inspection_num",
    ]

    feature_names = predictor_features + derived_features + station_features + safe_log_features
    # 确保所有特征列存在
    feature_names = [c for c in feature_names if c in df.columns]

    X = df[feature_names].copy()

    # 缺失值处理
    missing_count = X.isnull().sum().sum()
    if missing_count > 0:
        logger.info(f"缺失值总数: {missing_count}")
        for col in X.columns:
            if X[col].isnull().any():
                med = X[col].median()
                X[col].fillna(med, inplace=True)
                logger.info(f"  填充 {col} 缺失值: {X[col].isnull().sum()} 个 → 中位数 {med:.4f}")

    # 处理无穷值
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    for col in X.columns:
        if X[col].isnull().any():
            X[col].fillna(X[col].median(), inplace=True)

    # 标准化
    scaler = RobustScaler(quantile_range=(5, 95))
    X_scaled = scaler.fit_transform(X)
    X_scaled = pd.DataFrame(X_scaled, columns=feature_names, index=df.index)

    y = df[target_col].values

    logger.info(f"训练数据准备完成: X shape={X_scaled.shape}, "
                f"正样本率={y.mean()*100:.2f}%")
    logger.info(f"使用特征 ({len(feature_names)}个): {feature_names}")
    return X_scaled, y, feature_names, scaler


# =========================================================================
# 第五步：模型训练
# =========================================================================
def train_models(X_train, y_train, X_val, y_val, feature_names):
    """
    训练多个分类模型，返回训练好的模型字典。
    """
    logger.info("=" * 60)
    logger.info("开始模型训练...")
    logger.info("=" * 60)

    models = {}
    scale_pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    # ----- 1. XGBoost -----
    logger.info("\n[1/4] 训练 XGBoost...")
    xgb_model = xgb.XGBClassifier(
        n_estimators=500,
        max_depth=7,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        gamma=0.1,
        reg_alpha=0.1,
        reg_lambda=1.0,
        scale_pos_weight=scale_pos_weight,
        random_state=MODEL_SEED,
        n_jobs=N_JOBS,
        eval_metric="logloss",
        early_stopping_rounds=30,
        use_label_encoder=False,
        verbosity=0,
    )
    xgb_model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    models["XGBoost"] = xgb_model
    val_pred = xgb_model.predict_proba(X_val)[:, 1]
    logger.info(f"  XGBoost Val AUC: {roc_auc_score(y_val, val_pred):.4f}")

    # ----- 2. LightGBM -----
    logger.info("\n[2/4] 训练 LightGBM...")
    lgb_model = lgb.LGBMClassifier(
        n_estimators=800,
        max_depth=5,
        num_leaves=31,
        learning_rate=0.03,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        min_child_samples=50,
        min_child_weight=5,
        reg_alpha=0.5,
        reg_lambda=1.0,
        scale_pos_weight=scale_pos_weight,
        random_state=MODEL_SEED,
        n_jobs=N_JOBS,
        verbosity=-1,
    )
    lgb_model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="binary_logloss",
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
    )
    models["LightGBM"] = lgb_model
    val_pred = lgb_model.predict_proba(X_val)[:, 1]
    logger.info(f"  LightGBM Val AUC: {roc_auc_score(y_val, val_pred):.4f}")

    # ----- 3. Random Forest -----
    logger.info("\n[3/4] 训练 Random Forest...")
    rf_model = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_split=20,
        min_samples_leaf=10,
        class_weight="balanced",
        random_state=MODEL_SEED,
        n_jobs=N_JOBS,
        verbose=0,
    )
    rf_model.fit(X_train, y_train)
    models["RandomForest"] = rf_model
    val_pred = rf_model.predict_proba(X_val)[:, 1]
    logger.info(f"  RandomForest Val AUC: {roc_auc_score(y_val, val_pred):.4f}")

    # ----- 4. Logistic Regression (基线) -----
    logger.info("\n[4/4] 训练 Logistic Regression (基线)...")
    lr_model = LogisticRegression(
        class_weight="balanced",
        max_iter=5000,
        C=0.1,
        penalty="l2",
        random_state=MODEL_SEED,
        n_jobs=N_JOBS,
    )
    lr_model.fit(X_train, y_train)
    models["LogisticRegression"] = lr_model
    val_pred = lr_model.predict_proba(X_val)[:, 1]
    logger.info(f"  LogisticRegression Val AUC: {roc_auc_score(y_val, val_pred):.4f}")

    return models


# =========================================================================
# 第六步：模型评估
# =========================================================================
def evaluate_models(models, X_val, y_val, feature_names, output_dir: Path):
    """
    综合评估所有模型，生成对比报告和可视化。
    """
    logger.info("\n" + "=" * 60)
    logger.info("模型评估...")
    logger.info("=" * 60)

    results = []
    plt.style.use("ggplot")

    # ---- ROC 曲线 ----
    fig_roc, ax_roc = plt.subplots(figsize=(8, 6))
    ax_roc.plot([0, 1], [0, 1], "k--", alpha=0.4, label="Random / 随机猜测")

    # ---- PR 曲线 ----
    fig_pr, ax_pr = plt.subplots(figsize=(8, 6))

    colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12"]

    for idx, (name, model) in enumerate(models.items()):
        y_prob = model.predict_proba(X_val)[:, 1]

        # ---- 用 Youden's J 统计量寻找最优阈值 ----
        fpr, tpr, thresholds = roc_curve(y_val, y_prob)
        youden_j = tpr - fpr
        best_idx = np.argmax(youden_j)
        best_threshold = thresholds[best_idx]
        y_pred = (y_prob >= best_threshold).astype(int)

        # 指标
        auc = roc_auc_score(y_val, y_prob)
        ap = average_precision_score(y_val, y_prob)
        f1 = f1_score(y_val, y_pred)
        precision = precision_score(y_val, y_pred)
        recall = recall_score(y_val, y_pred)
        logloss_val = log_loss(y_val, y_prob)

        results.append({
            "Model": name,
            "Best Threshold": round(best_threshold, 4),
            "AUC": round(auc, 4),
            "Avg Precision": round(ap, 4),
            "F1": round(f1, 4),
            "Precision": round(precision, 4),
            "Recall": round(recall, 4),
            "Log Loss": round(logloss_val, 4),
        })

        # ROC
        fpr, tpr, _ = roc_curve(y_val, y_prob)
        ax_roc.plot(fpr, tpr, color=colors[idx % len(colors)],
                     lw=2, label=f"{name} (AUC={auc:.4f})")

        # PR
        prec, rec, _ = precision_recall_curve(y_val, y_prob)
        ax_pr.plot(rec, prec, color=colors[idx % len(colors)],
                    lw=2, label=f"{name} (AP={ap:.4f})")

    # ROC 美化（中英双语）
    ax_roc.set_xlabel("False Positive Rate / 假正率", fontsize=12)
    ax_roc.set_ylabel("True Positive Rate / 真正率", fontsize=12)
    ax_roc.set_title("ROC Curves — 风险预测模型对比", fontsize=14, fontweight="bold")
    ax_roc.legend(loc="lower right", fontsize=10)
    ax_roc.grid(True, alpha=0.3)
    fig_roc.tight_layout()
    fig_roc.savefig(output_dir / "roc_curves.png", dpi=150)
    logger.info(f"ROC 曲线已保存: {output_dir / 'roc_curves.png'}")
    plt.close(fig_roc)

    # PR 美化（中英双语）
    ax_pr.set_xlabel("Recall / 召回率", fontsize=12)
    ax_pr.set_ylabel("Precision / 精确率", fontsize=12)
    ax_pr.set_title("Precision-Recall Curves — 风险预测模型对比", fontsize=14, fontweight="bold")
    ax_pr.legend(loc="upper right", fontsize=10)
    ax_pr.grid(True, alpha=0.3)
    fig_pr.tight_layout()
    fig_pr.savefig(output_dir / "pr_curves.png", dpi=150)
    logger.info(f"PR 曲线已保存: {output_dir / 'pr_curves.png'}")
    plt.close(fig_pr)

    # ---- 对比表 ----
    result_df = pd.DataFrame(results).sort_values("AUC", ascending=False)
    logger.info(f"\n模型对比:\n{result_df.to_string(index=False)}")
    result_df.to_csv(output_dir / "model_comparison.csv", index=False, encoding="utf-8-sig")

    # ---- 混淆矩阵（使用最优阈值） ----
    best_name = result_df.iloc[0]["Model"]
    best_threshold = result_df.iloc[0]["Best Threshold"]
    best_model = models[best_name]
    y_best_prob = best_model.predict_proba(X_val)[:, 1]
    y_best_pred = (y_best_prob >= best_threshold).astype(int)

    fig_cm, ax_cm = plt.subplots(figsize=(6, 5))
    cm = confusion_matrix(y_val, y_best_pred)
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=["Low Risk / 低风险", "High Risk / 高风险"],
                yticklabels=["Low Risk / 低风险", "High Risk / 高风险"],
                ax=ax_cm)
    ax_cm.set_title(f"Confusion Matrix 混淆矩阵 — {best_name}", fontsize=13, fontweight="bold")
    ax_cm.set_xlabel("Predicted / 预测值")
    ax_cm.set_ylabel("Actual / 真实值")
    fig_cm.tight_layout()
    fig_cm.savefig(output_dir / "confusion_matrix.png", dpi=150)
    plt.close(fig_cm)

    return result_df, best_name


# =========================================================================
# 第七步：SHAP 可解释性
# =========================================================================
def shap_analysis(model, X, feature_names, output_dir: Path, model_name: str = "XGBoost"):
    """
    SHAP 特征重要性分析。
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"SHAP 可解释性分析 - {model_name}")
    logger.info("=" * 60)

    # 采样以加速 SHAP
    n_samples = min(2000, X.shape[0])
    X_sample = X.sample(n=n_samples, random_state=MODEL_SEED)
    logger.info(f"SHAP 采样: {n_samples} 行")

    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_sample)

        # 处理二分类输出的形状
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        if shap_values.ndim == 3:
            shap_values = shap_values[:, :, 1]

        # ---- 全局特征重要性 (条形图) ----
        fig_imp, ax_imp = plt.subplots(figsize=(10, 8))
        shap.summary_plot(
            shap_values, X_sample, feature_names=feature_names,
            plot_type="bar", show=False, max_display=20,
        )
        ax_imp = plt.gca()
        ax_imp.set_title(f"SHAP Feature Importance 特征重要性 — {model_name}", fontsize=14, fontweight="bold")
        fig_imp.tight_layout()
        fig_imp.savefig(output_dir / f"shap_importance_{model_name}.png", dpi=150, bbox_inches="tight")
        logger.info(f"SHAP 重要性已保存: {output_dir / f'shap_importance_{model_name}.png'}")
        plt.close(fig_imp)

        # ---- 蜂群图 ----
        fig_beeswarm, ax_bw = plt.subplots(figsize=(10, 7))
        shap.summary_plot(
            shap_values, X_sample, feature_names=feature_names,
            show=False, max_display=20,
        )
        ax_bw = plt.gca()
        ax_bw.set_title(f"SHAP Beeswarm 蜂群图 — {model_name}", fontsize=14, fontweight="bold")
        fig_beeswarm.tight_layout()
        fig_beeswarm.savefig(output_dir / f"shap_beeswarm_{model_name}.png", dpi=150, bbox_inches="tight")
        logger.info(f"SHAP 蜂群图已保存: {output_dir / f'shap_beeswarm_{model_name}.png'}")
        plt.close(fig_beeswarm)

        # ---- Top 特征的依赖图 ----
        feature_importance = np.abs(shap_values).mean(axis=0)
        top_features = np.argsort(feature_importance)[-6:][::-1]

        n_cols = 3
        n_rows = (len(top_features) + n_cols - 1) // n_cols
        fig_dep, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
        axes = axes.flatten()

        for i, feat_idx in enumerate(top_features):
            if i < len(axes):
                shap.dependence_plot(
                    feat_idx, shap_values, X_sample,
                    feature_names=feature_names,
                    show=False, ax=axes[i],
                )
                axes[i].set_title(f"SHAP Dependence 依赖: {feature_names[feat_idx]}", fontsize=10)

        # 隐藏多余的子图
        for j in range(i + 1, len(axes)):
            axes[j].set_visible(False)

        fig_dep.suptitle(f"SHAP Dependence Plots 依赖图 — {model_name}", fontsize=14, fontweight="bold")
        fig_dep.tight_layout()
        fig_dep.savefig(output_dir / f"shap_dependence_{model_name}.png", dpi=150, bbox_inches="tight")
        logger.info(f"SHAP 依赖图已保存: {output_dir / f'shap_dependence_{model_name}.png'}")
        plt.close(fig_dep)

    except Exception as e:
        logger.warning(f"SHAP 分析跳过 ({e})")

    return explainer


# =========================================================================
# 第八步：异常检测（无监督）
# =========================================================================
def anomaly_detection(df: pd.DataFrame, feature_names, scaler, output_dir: Path):
    """
    使用 Isolation Forest 进行无监督异常检测，
    发现不符合常规模式的可疑工单。
    """
    logger.info("\n" + "=" * 60)
    logger.info("异常检测 - Isolation Forest")
    logger.info("=" * 60)

    # 准备特征
    X_raw = df[feature_names].copy()
    X_raw.replace([np.inf, -np.inf], np.nan, inplace=True)
    X_raw.fillna(X_raw.median(), inplace=True)
    X_scaled = scaler.transform(X_raw)

    # 训练 Isolation Forest
    iso_forest = IsolationForest(
        n_estimators=200,
        contamination=0.05,  # 预期 5% 异常
        random_state=MODEL_SEED,
        n_jobs=N_JOBS,
        bootstrap=True,
    )
    anomaly_labels = iso_forest.fit_predict(X_scaled)
    anomaly_scores = iso_forest.score_samples(X_scaled)

    # 标注（-1=异常, 1=正常 → 1=异常, 0=正常）
    df_result = df.copy()
    df_result["anomaly_label"] = (anomaly_labels == -1).astype(int)
    df_result["anomaly_score"] = -anomaly_scores  # 越大越异常

    anomaly_rate = df_result["anomaly_label"].mean()
    logger.info(f"异常占比: {anomaly_rate*100:.2f}% (contamination=0.05)")

    # 分析异常样本在各维度的分布
    # （查看异常工单主要受哪些风险维度驱动）
    anomaly_samples = df_result[df_result["anomaly_label"] == 1]
    normal_samples = df_result[df_result["anomaly_label"] == 0]

    logger.info(f"\n异常样本 vs 正常样本 - 数值特征对比:")
    compare_cols = [
        "workorder_trvl_exp", "service_total_duration",
        "return_abolished_ratio", "people_num",
        "duration_per_person", "trvl_exp_per_person",
    ]
    compare_cols = [c for c in compare_cols if c in df_result.columns]
    for col in compare_cols:
        a_mean = anomaly_samples[col].mean()
        n_mean = normal_samples[col].mean()
        ratio = a_mean / (n_mean + 1e-6)
        logger.info(f"  {col:30s}: 异常={a_mean:>10.2f}, 正常={n_mean:>10.2f}, 比值={ratio:>6.2f}x")

    # ---------- 异常维度归因 ----------
    logger.info(f"\n异常工单维度归因 (与正常样本对比):")
    for col in compare_cols:
        a_mean = anomaly_samples[col].mean()
        n_mean = normal_samples[col].mean()
        pct_above = (anomaly_samples[col] > n_mean).mean() * 100
        logger.info(f"  {col:30s}: 异常均值={a_mean:>10.2f}, "
                    f"高于正常均值的异常占比={pct_above:>5.1f}%")

    # ---------- 保存结果 ----------
    outlier_cols = ["wo_id", "oil_station_id", "anomaly_label", "anomaly_score",
                    "risk_score_composite", "is_high_risk",
                    "workorder_trvl_exp", "service_total_duration",
                    "return_abolished_ratio", "duration_per_person"]
    outlier_cols = [c for c in outlier_cols if c in df_result.columns]
    df_result[outlier_cols].to_csv(
        output_dir / "anomaly_detection_result.csv", index=False, encoding="utf-8-sig"
    )
    logger.info(f"异常检测结果已保存: {output_dir / 'anomaly_detection_result.csv'}")

    # ---------- 可视化 ----------
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    axes = axes.flatten()

    # 1. 异常评分分布
    ax = axes[0]
    ax.hist(
        df_result[df_result["anomaly_label"] == 0]["anomaly_score"],
        bins=50, alpha=0.6, label="Normal / 正常", color="#2ecc71", density=True,
    )
    ax.hist(
        df_result[df_result["anomaly_label"] == 1]["anomaly_score"],
        bins=50, alpha=0.7, label="Anomaly / 异常", color="#e74c3c", density=True,
    )
    ax.set_xlabel("Anomaly Score 异常评分 (higher = more anomalous / 越高越异常)")
    ax.set_ylabel("Density / 密度")
    ax.set_title("Anomaly Score Distribution 异常评分分布", fontweight="bold")
    ax.legend()

    # 2. 异常 vs 综合风险评分
    ax = axes[1]
    ax.scatter(
        df_result[df_result["anomaly_label"] == 0]["risk_score_composite"],
        df_result[df_result["anomaly_label"] == 0]["anomaly_score"],
        s=5, alpha=0.3, label="Normal / 正常", color="#2ecc71",
    )
    ax.scatter(
        df_result[df_result["anomaly_label"] == 1]["risk_score_composite"],
        df_result[df_result["anomaly_label"] == 1]["anomaly_score"],
        s=15, alpha=0.7, label="Anomaly / 异常", color="#e74c3c",
    )
    ax.set_xlabel("Composite Risk Score / 综合风险评分")
    ax.set_ylabel("Anomaly Score / 异常评分")
    ax.set_title("Anomaly Score vs Risk Score 异常 vs 风险", fontweight="bold")
    ax.legend()

    # 3. 异常样本的成本 vs 时长
    ax = axes[2]
    ax.scatter(
        normal_samples["service_total_duration"],
        normal_samples["workorder_trvl_exp"],
        s=5, alpha=0.2, label="Normal / 正常", color="#2ecc71",
    )
    ax.scatter(
        anomaly_samples["service_total_duration"],
        anomaly_samples["workorder_trvl_exp"],
        s=15, alpha=0.6, label="Anomaly / 异常", color="#e74c3c",
    )
    ax.set_xlabel("Service Duration 服务时长 (hours / 小时)")
    ax.set_ylabel("Travel Expense / 差旅费")
    ax.set_title("Cost vs Duration 成本 vs 时长 — Anomaly Highlight 异常标注", fontweight="bold")
    ax.legend()

    # 4. 异常占比 vs 风险阈值
    ax = axes[3]
    risk_bins = pd.qcut(df_result["risk_score_composite"], q=10, duplicates="drop")
    anomaly_rate_by_risk = df_result.groupby(risk_bins, observed=True)["anomaly_label"].mean()
    anomaly_rate_by_risk.plot(kind="bar", ax=ax, color="#3498db", edgecolor="white")
    ax.set_xlabel("Composite Risk Decile / 综合风险十分位")
    ax.set_ylabel("Anomaly Rate / 异常占比")
    ax.set_title("Anomaly Rate by Risk Decile 各风险等级的异常比例", fontweight="bold")
    ax.set_xticklabels([f"Q{i+1}" for i in range(len(anomaly_rate_by_risk))], rotation=0)

    fig.suptitle("Anomaly Detection Analysis 异常检测分析", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "anomaly_analysis.png", dpi=150)
    logger.info(f"异常分析图已保存: {output_dir / 'anomaly_analysis.png'}")
    plt.close(fig)

    return df_result, iso_forest


# =========================================================================
# 第九步：EDA 探索性分析
# =========================================================================
def exploratory_analysis(df: pd.DataFrame, output_dir: Path):
    """
    数据探索性分析与可视化。
    """
    logger.info("\n" + "=" * 60)
    logger.info("探索性数据分析 (EDA)")
    logger.info("=" * 60)

    # ---- 1. 目标变量分布 ----
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    axes = axes.flatten()

    risk_cols = [
        ("workorder_trvl_exp", "工单差旅费分布 Travel Expense Distribution", "Travel Expense / 差旅费"),
        ("service_total_duration", "服务总时长分布 Duration Distribution", "Duration / 时长 (hours)"),
        ("return_abolished_ratio", "退回/作废占比分布 Return+Abandon Ratio", "Return+Abandon Ratio / 退回+作废率"),
        ("people_num", "工单人数分布 People Count Distribution", "People Count / 人数"),
        ("duration_per_person", "人均服务时长分布 Duration per Person", "Duration per Person / 人均时长"),
        ("trvl_exp_per_person", "人均差旅费分布 Cost per Person", "Cost per Person / 人均差旅费"),
    ]

    for i, (col, title, xlabel) in enumerate(risk_cols):
        if col not in df.columns:
            continue
        ax = axes[i]
        data = df[col].dropna().clip(upper=df[col].quantile(0.99))
        ax.hist(data, bins=60, color="#3498db", edgecolor="white", alpha=0.7)
        ax.axvline(data.median(), color="#e74c3c", ls="--", lw=2, label=f"Median 中位数={data.median():.1f}")
        ax.axvline(data.quantile(0.85), color="#f39c12", ls=":", lw=2, label=f"P85 高风险阈值={data.quantile(0.85):.1f}")
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Frequency / 频数")
        ax.set_title(title, fontweight="bold")
        ax.legend(fontsize=8)

    fig.suptitle("Key Risk Indicators Distribution 风险指标分布", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "eda_distributions.png", dpi=150)
    logger.info(f"EDA 分布图已保存: {output_dir / 'eda_distributions.png'}")
    plt.close(fig)

    # ---- 2. 相关性热图 ----
    corr_cols = NUMERIC_COLS + ["return_abolished_ratio", "duration_per_person",
                                 "trvl_exp_per_person", "service_scope"]
    corr_cols = [c for c in corr_cols if c in df.columns]
    corr = df[corr_cols].corr()

    fig_corr, ax_corr = plt.subplots(figsize=(14, 11))
    mask = np.triu(np.ones_like(corr, dtype=bool))
    cmap = sns.diverging_palette(230, 20, as_cmap=True)
    sns.heatmap(
        corr, mask=mask, cmap=cmap, center=0,
        square=True, linewidths=0.5,
        annot=False, fmt=".2f",
        cbar_kws={"shrink": 0.8},
        ax=ax_corr,
    )
    ax_corr.set_title("Feature Correlation Matrix 特征相关性矩阵", fontsize=14, fontweight="bold")
    fig_corr.tight_layout()
    fig_corr.savefig(output_dir / "eda_correlation.png", dpi=150)
    logger.info(f"相关性热图已保存: {output_dir / 'eda_correlation.png'}")
    plt.close(fig_corr)

    # ---- 3. 缺失值热图 ----
    missing = df[NUMERIC_COLS].isnull()
    if missing.any().any():
        fig_miss, ax_miss = plt.subplots(figsize=(12, 4))
        sns.heatmap(
            missing.T, cmap="RdYlGn_r", cbar=False,
            yticklabels=True, ax=ax_miss,
        )
        ax_miss.set_title("Missing Value Pattern 缺失值分布", fontweight="bold")
        ax_miss.set_xlabel("Samples / 样本")
        fig_miss.tight_layout()
        fig_miss.savefig(output_dir / "eda_missing.png", dpi=150)
        plt.close(fig_miss)

    # ---- 4. 高风险 vs 低风险对比 ----
    if "is_high_risk" in df.columns:
        compare_cols = [
            "workorder_trvl_exp", "service_total_duration",
            "return_abolished_ratio", "people_num",
            "duration_per_person", "trvl_exp_per_person",
            "repair_response_duration",
        ]
        compare_cols = [c for c in compare_cols if c in df.columns]

        fig_comp, axes_comp = plt.subplots(2, 4, figsize=(16, 8))
        axes_comp = axes_comp.flatten()

        for i, col in enumerate(compare_cols):
            if i >= len(axes_comp):
                break
            ax = axes_comp[i]
            high = df[df["is_high_risk"] == 1][col].dropna()
            low = df[df["is_high_risk"] == 0][col].dropna()
            ax.boxplot(
                [low, high],
                labels=["Low Risk / 低风险", "High Risk / 高风险"],
                widths=0.5,
                patch_artist=True,
                boxprops=dict(facecolor="#3498db", alpha=0.6),
                medianprops=dict(color="red", lw=2),
            )
            ax.set_title(col, fontsize=10, fontweight="bold")
            ax.set_ylabel("Value / 数值")

        for j in range(i + 1, len(axes_comp)):
            axes_comp[j].set_visible(False)

        fig_comp.suptitle("High Risk vs Low Risk 高风险 vs 低风险 — Feature Comparison 特征对比",
                          fontsize=14, fontweight="bold")
        fig_comp.tight_layout()
        fig_comp.savefig(output_dir / "eda_high_vs_low.png", dpi=150)
        logger.info(f"风险对比图已保存: {output_dir / 'eda_high_vs_low.png'}")
        plt.close(fig_comp)

    return True


# =========================================================================
# 第十步：保存模型与预测函数
# =========================================================================
def save_models(models, scaler, feature_names, output_dir: Path):
    """
    保存训练好的模型和预处理对象。
    """
    logger.info("\n保存模型...")
    import joblib

    model_path = output_dir / "models"
    model_path.mkdir(exist_ok=True)

    # 保存每个模型
    for name, model in models.items():
        path = model_path / f"{name}.pkl"
        joblib.dump(model, path)
        logger.info(f"  {name} → {path}")

    # 保存 Scaler
    scaler_path = model_path / "scaler.pkl"
    joblib.dump(scaler, scaler_path)
    logger.info(f"  Scaler → {scaler_path}")

    # 保存特征名
    feat_path = model_path / "feature_names.txt"
    with open(feat_path, "w", encoding="utf-8") as f:
        f.write("\n".join(feature_names))
    logger.info(f"  Feature names → {feat_path}")

    logger.info("模型保存完成！")
    return model_path


def load_models(model_dir: Path):
    """
    加载保存的模型和预处理器。
    """
    import joblib

    models = {}
    for p in model_dir.glob("*.pkl"):
        name = p.stem
        models[name] = joblib.load(p)

    scaler = joblib.load(model_dir / "scaler.pkl")

    with open(model_dir / "feature_names.txt", "r") as f:
        feature_names = [line.strip() for line in f if line.strip()]

    return models, scaler, feature_names


def predict_risk(
    new_data: pd.DataFrame,
    model_name: str = "XGBoost",
    model_dir: Path = None,
) -> pd.DataFrame:
    """
    对新数据进行风险预测。

    Args:
        new_data: 包含原始字段的 DataFrame
        model_name: 使用的模型名
        model_dir: 模型目录

    Returns:
        带有风险评分的 DataFrame
    """
    if model_dir is None:
        model_dir = OUTPUT_DIR / "models"

    models, scaler, feature_names = load_models(model_dir)

    if model_name not in models:
        raise KeyError(f"模型 {model_name} 不存在，可选: {list(models.keys())}")

    model = models[model_name]

    # 特征工程
    feat = engineer_features(new_data)

    # 检查特征
    missing_features = [c for c in feature_names if c not in feat.columns]
    if missing_features:
        raise ValueError(f"缺少特征: {missing_features}")

    X = feat[feature_names].copy()
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X.fillna(X.median(numeric_only=True), inplace=True)
    X_scaled = scaler.transform(X)

    # 预测
    proba = model.predict_proba(X_scaled)[:, 1]

    result = new_data[["wo_id", "oil_station_id"]].copy()
    result["risk_probability"] = proba
    result["risk_level"] = pd.cut(
        proba,
        bins=[0, 0.3, 0.7, 1.0],
        labels=["Low", "Medium", "High"],
    )
    return result


# =========================================================================
# 主流程
# =========================================================================
def run_pipeline():
    """
    执行完整的风险预测建模流程。
    """
    logger.info("=" * 60)
    logger.info("工业设备售后服务 - 风险预测系统")
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"输出目录: {OUTPUT_DIR}")
    logger.info("=" * 60)

    # 1. 加载数据
    df_raw = load_data(DATA_PATH)

    # 2. 特征工程
    df_feat = engineer_features(df_raw)

    # 2B. 油站聚合特征（在风险标签之前，仅使用预测器）
    df_feat = add_station_features(df_feat)

    # 3. 风险标签
    df_labeled = define_risk_labels(df_feat)

    # 4. EDA
    exploratory_analysis(df_labeled, OUTPUT_DIR)

    # 5. 准备训练数据
    X, y, feature_names, scaler = prepare_training_data(df_labeled)

    # 6. 训练/验证集划分（分层抽样）
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=MODEL_SEED, stratify=y,
    )
    logger.info(f"\n数据集划分: 训练 {len(X_train)} 行, 验证 {len(X_val)} 行")

    # 7. 模型训练
    models = train_models(X_train, y_train, X_val, y_val, feature_names)

    # 8. 模型评估
    result_df, best_name = evaluate_models(models, X_val, y_val, feature_names, OUTPUT_DIR)

    # 9. SHAP 分析（最佳模型）
    shap_analysis(models[best_name], X_val, feature_names, OUTPUT_DIR, best_name)

    # 10. 异常检测
    df_anomaly, iso_model = anomaly_detection(df_labeled, feature_names, scaler, OUTPUT_DIR)

    # 11. 保存模型
    model_path = save_models(models, scaler, feature_names, OUTPUT_DIR)

    # ---------- 输出摘要 ----------
    logger.info("\n" + "=" * 60)
    logger.info("✅ 风险预测建模完成！")
    logger.info("=" * 60)
    logger.info(f"\n最佳模型: {best_name} (AUC={result_df.iloc[0]['AUC']:.4f})")
    logger.info(f"\n输出文件:")
    logger.info(f"  模型:        {model_path}/")
    logger.info(f"  ROC 曲线:    {OUTPUT_DIR / 'roc_curves.png'}")
    logger.info(f"  PR 曲线:     {OUTPUT_DIR / 'pr_curves.png'}")
    logger.info(f"  混淆矩阵:    {OUTPUT_DIR / 'confusion_matrix.png'}")
    logger.info(f"  SHAP 重要性: {OUTPUT_DIR / f'shap_importance_{best_name}.png'}")
    logger.info(f"  异常分析:    {OUTPUT_DIR / 'anomaly_analysis.png'}")
    logger.info(f"  EDA 分布:    {OUTPUT_DIR / 'eda_distributions.png'}")
    logger.info(f"  异常结果:    {OUTPUT_DIR / 'anomaly_detection_result.csv'}")
    logger.info(f"  模型对比:    {OUTPUT_DIR / 'model_comparison.csv'}")

    return {
        "models": models,
        "scaler": scaler,
        "feature_names": feature_names,
        "best_model_name": best_name,
        "result_df": result_df,
        "df_labeled": df_labeled,
    }


# =========================================================================
# 命令行入口
# =========================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="工业设备售后服务风险预测系统")
    parser.add_argument("--data", type=str, default=str(DATA_PATH),
                        help="输入数据 CSV 文件路径")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR),
                        help="输出目录")
    parser.add_argument("--predict", type=str, default=None,
                        help="对新 CSV 文件进行预测")
    parser.add_argument("--model", type=str, default="XGBoost",
                        help="预测使用的模型名")
    parser.add_argument("--skip-eda", action="store_true",
                        help="跳过 EDA")

    args = parser.parse_args()

    if args.predict:
        # 预测模式
        data = pd.read_csv(args.predict)
        result = predict_risk(data, model_name=args.model)
        out_path = OUTPUT_DIR / "prediction_result.csv"
        result.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"预测结果已保存: {out_path}")
        print(result.head())
    else:
        # 完整训练流程
        DATA_PATH = Path(args.data)
        OUTPUT_DIR = Path(args.output)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        run_pipeline()
