# 📈 IBKR Trading Report Generator

This Python script is a tool for traders who use **Interactive Brokers (IBKR)**. It automates the process of generating a trading journal by connecting to the IBKR Client Gateway API, fetching trade data, calculating key performance metrics, and exporting a comprehensive report to an Excel spreadsheet.

---

## ✨ Key Features

- **Automated Data Fetching**: Connects directly to the IBKR Client Gateway API to retrieve all recent trade executions.
- **Intelligent P&L Calculation**: Matches buy and sell executions for the same instrument to calculate profit and loss on closed positions.
- **Consolidated Trade Log**: Groups multiple transactions for a single security into one consolidated entry, simplifying your journal and providing a clear overview of your trading activity.
- **Comprehensive Reporting**: Generates a detailed Excel file with essential trading metrics, including duration, sizing, and both gross and net P&L.
- **Open Positions Tracker**: Creates a separate sheet or file for all unmatched executions, helping you keep track of your currently open positions.
- **Easy Configuration**: All settings, including your account ID and output file name, are managed through a simple `config.yaml` file.

---

## 🚀 Getting Started

### Prerequisites

You need to have Python and the following libraries installed. You can install them using pip:

    pip install pandas requests pyyaml openpyxl

---

### IBKR Client Gateway and Certificate Setup

This script connects to the IBKR Client Gateway, which runs a local web server at https://localhost:5000. By default, the connection uses a self-signed certificate provided by IBKR.

For enhanced security and a seamless connection experience, it is highly recommended to use a locally trusted certificate. You can generate the necessary certificates for localhost using **mkcert**.

1. **Install mkcert**: Follow the instructions for your operating system on the official mkcert GitHub page.
    - **Windows**: install via [Chocolatey](https://chocolatey.org/install)  
    ```powershell
    choco install mkcert
    ```
3. **Generate a Trusted Certificate**: Run the following commands to create and install a locally trusted certificate for localhost:

        mkcert -install
        mkcert localhost 127.0.0.1 ::1
   
    This produces two files:
   - localhost.pem → the certificate
   - localhost-key.pem → the private key

4. **Install Java and Configure PATH**: The IBKR Gateway requires Java. Verify if it’s installed:
       ```java -version```
   Configure JAVA_HOME and PATH on Windows
   


7. **Use the Certificate**: When the script connects to the IBKR API, the `requests` library will automatically verify the connection using the certificate you generated, removing the need to disable SSL verification.

---

### Configuration

Before running the script, you must configure your account details. Create a file named `config.yaml` in the same directory as `generator.py` with the following content:

        # config.yaml
        account_id: 'your_account_id'
        output_file: 'ibkr_trade_log.xlsx'

Replace `'your_account_id'` with your actual IBKR account number.

---

## Running the IBKR Client Gateway Portal

1. Follow the instructions listed here: https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/#cp-tutorial
2. The gateway is included in the current repo, but you have to write your own config.yaml and conf.yaml files with your specific account information
3. Make sure you have JAVA installed and exported in the correct path
4. Execute the Gateway (from web API):

    `bin\run.bat root\conf.yaml`

    And in the case of Unix systems:

    `bin/run.sh root/conf.yaml`

Notes regarding setting up your own certifificate for connecting to localhost (this is not needed as there is no security concern)
- Chrome will say error because it doesn't recognize IBKR's default certificate since it is not issued from a Certificate Authority
---

## 🏃 Running the Script

1. Ensure that the **IBKR Client Gateway** is running and you are logged into your trading account.
2. Navigate to the script's directory in your terminal or command prompt.
3. Execute the script using the following command:

        python generator.py

The script will print its progress to the console. Upon completion, you will find `ibkr_trade_log.xlsx` and `ibkr_trade_log_open_positions.xlsx` in the same directory.

