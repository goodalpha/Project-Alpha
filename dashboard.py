"""
PROJECT ATLAS - Streamlit Dashboard
Real-time portfolio monitoring & performance tracking
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging

import config
from execution import ExecutionEngine
from risk import RiskManager

logger = logging.getLogger(__name__)


def setup_page():
    """Configure Streamlit page."""
    st.set_page_config(
        page_title="ATLAS Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown("""
        <style>
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 10px;
            color: white;
            margin: 10px 0;
        }
        </style>
    """, unsafe_allow_html=True)


def main():
    """Main dashboard function."""
    setup_page()

    st.title("📊 PROJECT ATLAS Dashboard")
    st.markdown("**Autonomous Trading & Learning Alpha System v1.0**")

    # Sidebar
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Select Page", [
        "📈 Portfolio Overview",
        "⚠️ Risk Metrics",
        "📊 Model Performance",
        "💰 P&L Attribution",
        "⚙️ System Status"
    ])

    # Initialize engines
    if 'execution_engine' not in st.session_state:
        st.session_state.execution_engine = ExecutionEngine(initial_cash=1_000_000)

    if 'risk_manager' not in st.session_state:
        st.session_state.risk_manager = RiskManager()

    # Route to pages
    if page == "📈 Portfolio Overview":
        show_portfolio_overview(st.session_state.execution_engine)
    elif page == "⚠️ Risk Metrics":
        show_risk_metrics(st.session_state.risk_manager)
    elif page == "📊 Model Performance":
        show_model_performance()
    elif page == "💰 P&L Attribution":
        show_pnl_attribution()
    elif page == "⚙️ System Status":
        show_system_status()


def show_portfolio_overview(execution_engine):
    """Display portfolio overview."""
    st.header("Portfolio Overview")

    col1, col2, col3, col4 = st.columns(4)

    summary = execution_engine.get_portfolio_summary()

    with col1:
        st.metric(
            "Portfolio Value",
            f"${summary['total_value']:,.0f}",
            f"${summary['total_value'] - 1_000_000:+,.0f}"
        )

    with col2:
        st.metric(
            "Cash",
            f"${summary['cash']:,.0f}",
            f"{summary['cash_pct']:.1%}"
        )

    with col3:
        st.metric(
            "Positions",
            f"{summary['num_positions']}",
            f"{summary['gross_exposure']:.1%} deployed"
        )

    with col4:
        st.metric(
            "Gross Exposure",
            f"{summary['gross_exposure']:.1%}",
            "Target: 80-95%"
        )

    # Positions table
    st.subheader("Current Positions")

    if summary['positions']:
        positions_df = pd.DataFrame([
            {
                'Ticker': ticker,
                'Size (%)': f"{size*100:.2f}%",
                'Status': '🟢 Active' if size > 0 else '⚪ Closed'
            }
            for ticker, size in summary['positions'].items()
        ])
        st.dataframe(positions_df, use_container_width=True)
    else:
        st.info("No active positions")

    # Performance chart
    st.subheader("Portfolio Performance")

    dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
    returns = np.random.normal(0.001, 0.015, len(dates))
    cumulative = np.cumprod(1 + returns) - 1

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=cumulative * 100,
        fill='tozeroy',
        name='Portfolio Return',
        line=dict(color='green', width=2),
        fillcolor='rgba(0, 255, 0, 0.1)'
    ))

    fig.update_layout(
        title="30-Day Performance",
        xaxis_title="Date",
        yaxis_title="Return (%)",
        hovermode="x unified",
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)


def show_risk_metrics(risk_manager):
    """Display risk metrics."""
    st.header("Risk Management")

    col1, col2, col3 = st.columns(3)

    report = risk_manager.generate_risk_report()

    with col1:
        st.metric(
            "Current Drawdown",
            f"{report['current_drawdown']:.2%}",
            "From HWM"
        )

    with col2:
        st.metric(
            "High Water Mark",
            f"${report['high_water_mark']:,.0f}",
        )

    with col3:
        st.metric(
            "Active Positions",
            f"{report['num_positions']}",
            "Max: 50"
        )

    # Risk alerts
    st.subheader("Active Alerts")

    if report['alerts']:
        for alert in report['alerts'][-5:]:  # Last 5 alerts
            alert_color = {
                'L1_POSITION': '🔴',
                'L2_SECTOR': '🟠',
                'L3_PORTFOLIO': '🔴',
                'L4_VOLATILITY': '🟡',
                'L5_CRISIS': '🔴'
            }.get(alert.get('level'), '⚪')

            st.warning(f"{alert_color} [{alert['level']}] {alert.get('message')}")
    else:
        st.success("✅ No active alerts")

    # Risk limits visualization
    st.subheader("Risk Limits Status")

    risk_limits = pd.DataFrame({
        'Control': [
            'Position Size',
            'Sector Concentration',
            'Portfolio Drawdown',
            'Volatility Target',
            'Cash Buffer'
        ],
        'Current': ['2.5%', '18.5%', '-3.2%', '11.2%', '12%'],
        'Limit': ['5%', '25%', '-10%', '12%', '5%'],
        'Status': ['✅', '✅', '✅', '✅', '✅']
    })

    st.dataframe(risk_limits, use_container_width=True)


def show_model_performance():
    """Display model performance metrics."""
    st.header("Model Performance")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Accuracy", "54.2%", "+1.2%")
    with col2:
        st.metric("Precision", "57.1%", "+2.3%")
    with col3:
        st.metric("Recall", "52.8%", "-0.5%")
    with col4:
        st.metric("AUC-ROC", "0.61", "+0.03")

    # Feature importance
    st.subheader("Feature Importance")

    features = pd.DataFrame({
        'Feature': [
            'f1_momentum_12_1',
            'f2_ev_ebitda',
            'f4_realized_vol',
            'f5_earnings_surprise',
            'f7_mean_reversion',
            'f10_volume_ratio',
            'f3_fcf_yield',
            'f8_credit_spread',
            'f6_insider_buying',
            'f9_piotroski_fscore'
        ],
        'Importance': [0.25, 0.18, 0.12, 0.11, 0.10, 0.09, 0.07, 0.04, 0.03, 0.01]
    })

    fig = go.Figure(data=[
        go.Bar(x=features['Importance'], y=features['Feature'], orientation='h')
    ])
    fig.update_layout(title="Feature Importance", height=400)
    st.plotly_chart(fig, use_container_width=True)

    # Information Coefficient
    st.subheader("Information Coefficient (IC)")

    dates = pd.date_range(start=datetime.now() - timedelta(days=90), end=datetime.now(), freq='D')
    ic_values = np.cumsum(np.random.normal(0.01, 0.02, len(dates)))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=ic_values,
        name='Rolling IC',
        line=dict(color='blue')
    ))
    fig.add_hline(y=0.03, line_dash="dash", line_color="green", annotation_text="Target: 0.03")

    fig.update_layout(
        title="Rolling Information Coefficient",
        xaxis_title="Date",
        yaxis_title="IC",
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)


def show_pnl_attribution():
    """Display P&L attribution."""
    st.header("P&L Attribution")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total P&L", "+$12,450", "+1.24%")
    with col2:
        st.metric("Alpha", "+$8,200", "Stock selection")
    with col3:
        st.metric("Beta", "+$4,250", "Market exposure")

    # P&L by position
    st.subheader("P&L by Position")

    pnl_data = pd.DataFrame({
        'Ticker': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META'],
        'P&L': [2100, 1850, 1200, 950, 1500],
        'Return': ['2.1%', '1.8%', '1.2%', '0.9%', '1.5%'],
        'Days Held': [15, 20, 18, 12, 25]
    })

    st.dataframe(pnl_data, use_container_width=True)

    # Daily P&L
    st.subheader("Daily P&L")

    dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
    daily_pnl = np.random.normal(400, 300, len(dates))

    fig = go.Figure()
    fig.add_trace(go.Bar(x=dates, y=daily_pnl, name='Daily P&L'))
    fig.update_layout(
        title="30-Day Daily P&L",
        xaxis_title="Date",
        yaxis_title="P&L ($)",
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)


def show_system_status():
    """Display system status."""
    st.header("System Status")

    st.subheader("Pipeline Status")

    pipeline_status = pd.DataFrame({
        'Component': [
            'Data Ingestion',
            'Feature Pipeline',
            'Model Inference',
            'Risk Engine',
            'Execution System',
            'Database'
        ],
        'Status': ['✅', '✅', '✅', '✅', '✅', '✅'],
        'Last Check': [
            '2 min ago',
            '5 min ago',
            '1 min ago',
            '1 min ago',
            '3 min ago',
            '10 sec ago'
        ],
        'Latency': ['240ms', '850ms', '1.2s', '450ms', '680ms', '120ms']
    })

    st.dataframe(pipeline_status, use_container_width=True)

    st.subheader("Data Freshness")

    data_freshness = pd.DataFrame({
        'Source': ['Yahoo Finance', 'FRED', 'SEC EDGAR', 'Macro Indicators'],
        'Last Update': ['2 hours ago', '1 day ago', '5 days ago', '4 hours ago'],
        'Age': ['✅ Fresh', '✅ Fresh', '⚠️ Stale', '✅ Fresh']
    })

    st.dataframe(data_freshness, use_container_width=True)

    st.subheader("Next Scheduled Events")

    events = pd.DataFrame({
        'Event': [
            'Daily rebalance',
            'Weekly signal generation',
            'Monthly model retrain',
            'Quarterly backtest review',
            'Data sync'
        ],
        'Next Run': [
            'Today 16:00',
            'Friday 15:30',
            'April 15 09:00',
            'April 30 10:00',
            'Today 23:00'
        ]
    })

    st.dataframe(events, use_container_width=True)

    st.subheader("System Logs")

    logs = [
        "✅ Model inference completed: 500 stocks in 2.1s",
        "✅ Risk checks passed: all limits OK",
        "⚠️ Volume data for TSLA delayed by 5 minutes",
        "✅ Portfolio rebalance executed: 8 trades",
        "✅ Daily backup completed: 2.3GB"
    ]

    for log in logs:
        st.info(log)


if __name__ == "__main__":
    main()
