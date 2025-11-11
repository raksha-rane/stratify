"""
Integration Tests for AQUA
Tests end-to-end functionality
"""
import pytest
import requests
import time
import json

# Service URLs
DATA_SERVICE_URL = 'http://localhost:5001'
STRATEGY_SERVICE_URL = 'http://localhost:5002'

# Test configuration
TEST_TICKER = 'AAPL'
TEST_START_DATE = '2023-01-01'
TEST_END_DATE = '2023-12-31'
TEST_INITIAL_CAPITAL = 10000


class TestDataService:
    """Test Data Service endpoints"""
    
    def test_health_check(self):
        """Test data service health check"""
        try:
            response = requests.get(f'{DATA_SERVICE_URL}/health', timeout=5)
            assert response.status_code == 200
            assert response.json()['status'] == 'healthy'
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Data service not available: {type(e).__name__} - {str(e)}")
    
    def test_fetch_data(self):
        """Test data fetching"""
        try:
            response = requests.post(
                f'{DATA_SERVICE_URL}/data/fetch',
                json={
                    'ticker': TEST_TICKER,
                    'start_date': TEST_START_DATE,
                    'end_date': TEST_END_DATE
                },
                timeout=30
            )
            
            assert response.status_code == 200
            data = response.json()
            assert 'ticker' in data
            assert data['ticker'] == TEST_TICKER
            assert 'records' in data
            assert data['records'] > 0
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Data service not available: {type(e).__name__} - {str(e)}")
    
    def test_get_data(self):
        """Test retrieving stored data"""
        try:
            # First fetch data
            requests.post(
                f'{DATA_SERVICE_URL}/data/fetch',
                json={
                    'ticker': TEST_TICKER,
                    'start_date': TEST_START_DATE,
                    'end_date': TEST_END_DATE
                },
                timeout=30
            )
            
            # Then retrieve it
            response = requests.get(
                f'{DATA_SERVICE_URL}/data/get',
                params={
                    'ticker': TEST_TICKER,
                    'start_date': TEST_START_DATE,
                    'end_date': TEST_END_DATE
                },
                timeout=10
            )
            
            assert response.status_code == 200
            data = response.json()
            assert 'data' in data
            assert len(data['data']) > 0
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Data service not available: {type(e).__name__} - {str(e)}")


class TestStrategyEngine:
    """Test Strategy Engine endpoints"""
    
    def test_health_check(self):
        """Test strategy engine health check"""
        try:
            response = requests.get(f'{STRATEGY_SERVICE_URL}/health', timeout=5)
            assert response.status_code == 200
            assert response.json()['status'] == 'healthy'
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Strategy engine not available: {type(e).__name__} - {str(e)}")
    
    def test_sma_strategy(self):
        """Test SMA strategy execution"""
        try:
            # First ensure data is available
            requests.post(
                f'{DATA_SERVICE_URL}/data/fetch',
                json={
                    'ticker': TEST_TICKER,
                    'start_date': TEST_START_DATE,
                    'end_date': TEST_END_DATE
                },
                timeout=30
            )
            
            # Run strategy
            response = requests.post(
                f'{STRATEGY_SERVICE_URL}/strategy/run',
                json={
                    'ticker': TEST_TICKER,
                    'strategy': 'sma',
                    'start_date': TEST_START_DATE,
                    'end_date': TEST_END_DATE,
                    'parameters': {
                        'short_window': 20,
                        'long_window': 50
                    },
                    'initial_capital': TEST_INITIAL_CAPITAL
                },
                timeout=60
            )
            
            assert response.status_code == 200
            result = response.json()
            assert 'metrics' in result
            assert 'total_return' in result['metrics']
            assert 'sharpe_ratio' in result['metrics']
            assert 'equity_curve' in result
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Services not available: {type(e).__name__} - {str(e)}")
    
    def test_mean_reversion_strategy(self):
        """Test mean reversion strategy execution"""
        try:
            response = requests.post(
                f'{STRATEGY_SERVICE_URL}/strategy/run',
                json={
                    'ticker': TEST_TICKER,
                    'strategy': 'mean_reversion',
                    'start_date': TEST_START_DATE,
                    'end_date': TEST_END_DATE,
                    'parameters': {
                        'window': 20,
                        'num_std': 2
                    },
                    'initial_capital': TEST_INITIAL_CAPITAL
                },
                timeout=60
            )
            
            assert response.status_code == 200
            result = response.json()
            assert 'metrics' in result
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Services not available: {type(e).__name__} - {str(e)}")
    
    def test_momentum_strategy(self):
        """Test momentum strategy execution"""
        try:
            response = requests.post(
                f'{STRATEGY_SERVICE_URL}/strategy/run',
                json={
                    'ticker': TEST_TICKER,
                    'strategy': 'momentum',
                    'start_date': TEST_START_DATE,
                    'end_date': TEST_END_DATE,
                    'parameters': {
                        'lookback': 10
                    },
                    'initial_capital': TEST_INITIAL_CAPITAL
                },
                timeout=60
            )
            
            assert response.status_code == 200
            result = response.json()
            assert 'metrics' in result
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Services not available: {type(e).__name__} - {str(e)}")
    
    def test_list_results(self):
        """Test listing backtest results"""
        try:
            response = requests.get(f'{STRATEGY_SERVICE_URL}/results', timeout=10)
            
            assert response.status_code == 200
            data = response.json()
            assert 'results' in data
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Strategy engine not available: {type(e).__name__} - {str(e)}")


class TestEndToEnd:
    """Test end-to-end workflows"""
    
    def test_complete_workflow(self):
        """Test complete workflow from data fetch to strategy execution"""
        try:
            # Step 1: Fetch data
            fetch_response = requests.post(
                f'{DATA_SERVICE_URL}/data/fetch',
                json={
                    'ticker': TEST_TICKER,
                    'start_date': TEST_START_DATE,
                    'end_date': TEST_END_DATE
                },
                timeout=30
            )
            assert fetch_response.status_code == 200
            
            # Step 2: Run strategy
            strategy_response = requests.post(
                f'{STRATEGY_SERVICE_URL}/strategy/run',
                json={
                    'ticker': TEST_TICKER,
                    'strategy': 'sma',
                    'start_date': TEST_START_DATE,
                    'end_date': TEST_END_DATE,
                    'parameters': {
                        'short_window': 20,
                        'long_window': 50
                    },
                    'initial_capital': TEST_INITIAL_CAPITAL
                },
                timeout=60
            )
            assert strategy_response.status_code == 200
            
            # Step 3: Verify results
            result = strategy_response.json()
            assert result['metrics']['initial_capital'] == TEST_INITIAL_CAPITAL
            assert 'final_capital' in result['metrics']
            assert len(result['equity_curve']) > 0
            
            # Step 4: List results
            list_response = requests.get(f'{STRATEGY_SERVICE_URL}/results', timeout=10)
            assert list_response.status_code == 200
            assert len(list_response.json()['results']) > 0
            
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Services not available: {type(e).__name__} - {str(e)}")


if __name__ == '__main__':
    print("Running integration tests...")
    print("Make sure all services are running before executing these tests.")
    print("Run: docker-compose up -d")
    time.sleep(2)
    pytest.main([__file__, '-v', '--tb=short'])
