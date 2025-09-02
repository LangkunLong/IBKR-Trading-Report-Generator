# 📈 IBKR Trading Report Generator

This Python script is a tool for traders who use Interactive Brokers (IBKR). It automates the process of generating a trading journal by connecting to the IBKR Client Gateway API, fetching trade data, calculating key performance metrics, and exporting a comprehensive report to an Excel spreadsheet.

## ✨ Key Features

* **Automated Data Fetching**: Connects directly to the IBKR Client Gateway API to retrieve all recent trade executions.

* **Intelligent P&L Calculation**: The script is designed to match buy and sell executions for the same instrument to calculate the profit and loss on closed positions.

* **Consolidated Trade Log**: It groups multiple transactions for a single security into one consolidated entry, simplifying your journal and providing a clear overview of your trading activity.

* **Comprehensive Reporting**: Generates a detailed Excel file with essential trading metrics, including duration, sizing, and both gross and net P&L.

* **Open Positions Tracker**: Creates a separate sheet or file for all unmatched executions, helping you keep track of your currently open positions.

* **Easy Configuration**: All settings, including your account ID and output file name, are managed through a simple `config.yaml` file.

## 🚀 Getting Started

### Prerequisites

You need to have Python and the following libraries installed. You can install them using `pip`:
