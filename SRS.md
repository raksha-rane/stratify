# 🧾 **Software Requirements Specification (SRS)**

## For: Automated Quant Trading Strategy Platform (AQTS)

**Version:** 1.0  
**Date:** November 2025
---

## **1. Introduction**

### **1.1 Purpose**

The purpose of this document is to define the requirements and specifications for the **Automated Quant Trading Strategy Platform (AQTS)** — a system designed to simulate, evaluate, and visualize algorithmic trading strategies.

This project demonstrates a **complete software lifecycle**, including:

* Quant strategy development,
* Data ingestion and storage,
* Automated backtesting and performance evaluation,
* CI/CD automation using Jenkins,
* Containerized deployment using Docker.

It serves as a practical and educational demonstration of how DevOps principles integrate with quantitative finance applications.

---

### **1.2 Scope**

**AQTS** is an end-to-end **local trading research platform** that:

* Fetches live or historical market data (e.g., via Yahoo Finance API).
* Executes quantitative trading strategies (momentum, mean reversion, SMA crossover).
* Simulates trades and calculates performance metrics (PnL, Sharpe ratio, drawdown).
* Stores data and results in a local database.
* Provides a **web dashboard** for visualization.
* Automates builds, tests, and deployments using Jenkins pipelines and Docker.

No real trades are executed — the platform is for **simulation and analytics only**.

---

### **1.3 Definitions, Acronyms, and Abbreviations**

| Term  | Description                                    |
| ----- | ---------------------------------------------- |
| AQTS  | Automated Quant Trading Strategy               |
| API   | Application Programming Interface              |
| CI/CD | Continuous Integration / Continuous Deployment |
| SMA   | Simple Moving Average                          |
| PnL   | Profit and Loss                                |
| UI    | User Interface                                 |
| DB    | Database                                       |

---

### **1.4 References**

* Yahoo Finance API documentation
* Python Libraries: `pandas`, `numpy`, `ta`, `matplotlib`, `flask`, `sqlalchemy`
* Jenkins Documentation (latest LTS version)
* Docker Documentation

---

### **1.5 Overview**

The remainder of this document describes the **overall system architecture, features, constraints, design goals**, and **functional and non-functional requirements**.

---

## **2. Overall Description**

### **2.1 Product Perspective**

AQTS is a **modular system** comprising five major components:

1. **Data Service** – Fetches and preprocesses stock data.
2. **Strategy Engine** – Runs trading algorithms on the data.
3. **Backtesting Module** – Simulates trades and computes performance metrics.
4. **Visualization Dashboard** – Displays results and analytics interactively.
5. **Automation Pipeline** – Handles build, testing, and deployment via Jenkins.

Each module runs in a **Docker container**, and all containers communicate via REST APIs.

---

### **2.2 Product Features**

| Feature                     | Description                                                                              |
| --------------------------- | ---------------------------------------------------------------------------------------- |
| **Data Fetching**           | Pulls historical and near-real-time market data for selected tickers.                    |
| **Strategy Selection**      | Allows choosing between predefined strategies (SMA Crossover, Mean Reversion, Momentum). |
| **Backtesting Engine**      | Simulates strategy performance on historical data.                                       |
| **Performance Metrics**     | Calculates PnL, Sharpe Ratio, Max Drawdown, Win Rate.                                    |
| **Interactive Dashboard**   | Displays results, charts, and statistics.                                                |
| **Configurable Parameters** | User can set date range, tickers, and strategy parameters.                               |
| **Containerized Services**  | Each module is Dockerized for isolated and reproducible environments.                    |
| **CI/CD Pipeline**          | Jenkins automates build, test, and deployment of new strategy code.                      |

---

### **2.3 User Classes and Characteristics**

| User Class           | Description                        | Technical Skill |
| -------------------- | ---------------------------------- | --------------- |
| **Quant Researcher** | Tests and evaluates strategies.    | High            |
| **Developer**        | Modifies algorithms and pipelines. | High            |
| **Student/Viewer**   | Views results on dashboard.        | Medium          |

---

### **2.4 Operating Environment**

* OS: Ubuntu 22.04 LTS / Windows 11
* Backend: Python 3.11
* Frontend: React.js (minimal) or Streamlit
* Database: PostgreSQL 15
* Containerization: Docker 25.x
* CI/CD: Jenkins LTS
* Visualization: Plotly, Matplotlib
* Message Queue (optional): Redis
* Version Control: Git + GitHub (local or remote)

---

### **2.5 Design and Implementation Constraints**

* No real money or live brokerage APIs (simulation only).
* Entire stack must run locally (no AWS, no external DB).
* Must support offline operation (historical data).
* Limited to open-source technologies.

---

### **2.6 User Documentation**

* **README.md** — setup and usage instructions
* **API Documentation** — via Swagger (Flask-RESTX)
* **Developer Guide** — Jenkinsfile, Docker Compose, strategy guide

---

### **2.7 Assumptions and Dependencies**

* User has Docker and Jenkins installed locally.
* Stable internet connection for fetching initial data (Yahoo Finance).
* Data fetched is reliable and consistent.

---

## **3. System Features**

### **3.1 Data Ingestion Module**

**Description:**  
Fetches stock data and preprocesses it for the Strategy Engine.

**Functional Requirements:**

1. System shall fetch OHLCV (Open, High, Low, Close, Volume) data via Yahoo Finance API.
2. System shall allow the user to specify tickers and time range.
3. System shall clean and store data in PostgreSQL.

**Inputs:**  
Ticker, start date, end date

**Outputs:**  
Cleaned dataset stored in DB

**Interfaces:**  
REST API endpoint `/data/fetch`

---

### **3.2 Strategy Engine**

**Description:**  
Implements trading strategies and generates buy/sell signals.

**Strategies Implemented:**

1. **Simple Moving Average (SMA) Crossover** – Buy when short SMA crosses above long SMA, sell when below.
2. **Mean Reversion Strategy** – Buy when price < moving average − std, sell when price > moving average + std.
3. **Momentum Strategy** – Go long if returns are positive for last N days, short otherwise.

**Functional Requirements:**

1. Strategy parameters shall be configurable.
2. Each strategy shall produce trade signals for backtesting.
3. System shall allow easy extension for new strategies.

**Interfaces:**  
`/strategy/run`

---

### **3.3 Backtesting and Analytics Module**

**Description:**  
Simulates execution of signals on historical data and computes performance metrics.

**Functional Requirements:**

1. Compute trade-by-trade PnL.
2. Calculate Sharpe ratio, maximum drawdown, and win rate.
3. Store results and summary statistics in DB.
4. Provide JSON response for visualization layer.

---

### **3.4 Visualization Dashboard**

**Description:**  
Frontend to visualize performance, strategies, and metrics.

**Functional Requirements:**

1. Display equity curve, trade points, and metrics.
2. Provide controls for strategy selection, date range, and ticker input.
3. Fetch and display results from API.
4. Refresh dynamically when new backtests are run.

**Tech:**  
Streamlit (preferred for simplicity) or React.js frontend fetching from Flask API.

---

### **3.5 Automation & CI/CD Module**

**Description:**  
Implements DevOps lifecycle using Jenkins and Docker.

**Functional Requirements:**

1. Jenkinsfile defines stages:
   * **Build:** Docker image creation.
   * **Test:** Unit + integration tests on strategies.
   * **Deploy:** Spin up updated containers using Docker Compose.
2. System shall automatically test all strategies on new commits.
3. System shall roll back in case of test failure.
4. Jenkins dashboard shall display build status and logs.

---

## **4. External Interface Requirements**

### **4.1 User Interfaces**

* **Streamlit Web UI:** Simple dashboard with:
  * Input forms for ticker and parameters
  * Buttons to run strategy and backtest
  * Charts and metrics display

### **4.2 Software Interfaces**

* Yahoo Finance API
* PostgreSQL DB
* REST APIs between services

### **4.3 Hardware Interfaces**

* Local machine with 8GB+ RAM and internet connection.

---

## **5. Non-Functional Requirements**

| Type                | Requirement                                                        |
| ------------------- | ------------------------------------------------------------------ |
| **Performance**     | Should process one backtest under 5 seconds for 1-year data.       |
| **Scalability**     | Modular microservices allow adding more strategies easily.         |
| **Reliability**     | Automatic tests ensure correctness before deployment.              |
| **Security**        | Local-only execution; no external user access.                     |
| **Maintainability** | Docker images and modular Python codebase ease updates.            |
| **Usability**       | Streamlit dashboard should be intuitive with minimal input fields. |

---

## **6. System Architecture**

**Architecture Components:**

1. **Flask API (Backend)**
   * `/data/fetch`
   * `/strategy/run`
   * `/results`
2. **PostgreSQL Database**
   * Tables: `market_data`, `trades`, `metrics`
3. **Streamlit Dashboard**
   * Frontend visualization layer
4. **Dockerized Microservices**
   * `data-service`, `strategy-engine`, `dashboard`, `postgres-db`
5. **Jenkins CI/CD Pipeline**
   * Stages: Build → Test → Deploy

**Diagram (Conceptual):**

```
[User] → [Streamlit UI] → [Flask Backend] → [PostgreSQL]
                                  ↑
                                  │
                       [Strategy Engine Container]
                                  ↑
                       [Data Fetcher Container]
                                  │
                             [Yahoo Finance]
```

---

## **7. System Design Deliverables**

1. **SRS Document (this)**
2. **System Architecture Diagram (DFD, ERD)**
3. **Docker Compose YAML**
4. **Jenkinsfile (Pipeline Script)**
5. **Source Code (Python + Streamlit)**
6. **README.md & Setup Guide**
7. **Sample Test Reports**

---

## **8. Future Enhancements**

* Add Reinforcement Learning or LSTM-based strategies.
* Introduce Redis caching for faster backtesting.
* Include Telegram/Email alert system.
* Add container orchestration via Kubernetes (advanced version).

---

✅ **Summary:**  
The **Automated Quant Trading Strategy Platform** is a clean, fully modular, DevOps-compliant quant project that can be built and demoed entirely on a local system using Docker and Jenkins. It demonstrates data ingestion, algorithmic computation, analytics visualization, and automated deployment — making it ideal for a **final-year DevOps assignment**.
