"""
Unit Tests for Data Validators Module
Tests data validation, quality scoring, and outlier detection
"""
import pytest
import pandas as pd
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_service.validators import (
    validate_ticker_format,
    validate_date_range,
    validate_ohlcv_data,
    DataQualityReport
)


class TestTickerValidation:
    """Test ticker format validation"""
    
    def test_valid_ticker(self):
        """Test valid ticker formats"""
        assert validate_ticker_format('AAPL') is True
        assert validate_ticker_format('MSFT') is True
        assert validate_ticker_format('BRK.B') is True
        assert validate_ticker_format('SPY') is True
    
    def test_invalid_ticker_lowercase(self):
        """Test lowercase ticker"""
        with pytest.raises(ValueError, match="must be uppercase"):
            validate_ticker_format('aapl')
    
    def test_invalid_ticker_empty(self):
        """Test empty ticker"""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_ticker_format('')
    
    def test_invalid_ticker_too_long(self):
        """Test ticker too long"""
        with pytest.raises(ValueError, match="cannot exceed 10 characters"):
            validate_ticker_format('VERYLONGTICKER')
    
    def test_invalid_ticker_special_chars(self):
        """Test ticker with invalid characters"""
        with pytest.raises(ValueError, match="Invalid characters"):
            validate_ticker_format('AAP$L')


class TestDateRangeValidation:
    """Test date range validation"""
    
    def test_valid_date_range(self):
        """Test valid date range"""
        start = '2023-01-01'
        end = '2023-12-31'
        assert validate_date_range(start, end) is True
    
    def test_end_before_start(self):
        """Test end date before start date"""
        start = '2023-12-31'
        end = '2023-01-01'
        with pytest.raises(ValueError, match="cannot be before start_date"):
            validate_date_range(start, end)
    
    def test_future_dates(self):
        """Test future dates"""
        start = '2023-01-01'
        future_end = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
        with pytest.raises(ValueError, match="cannot be in the future"):
            validate_date_range(start, future_end)
    
    def test_invalid_date_format(self):
        """Test invalid date format"""
        with pytest.raises(ValueError, match="Invalid date format"):
            validate_date_range('01/01/2023', '12/31/2023')
    
    def test_date_range_too_long(self):
        """Test date range exceeding maximum"""
        start = '2000-01-01'
        end = '2023-12-31'
        with pytest.raises(ValueError, match="exceeds maximum"):
            validate_date_range(start, end, max_days=365)


class TestOHLCVValidation:
    """Test OHLCV data validation"""
    
    def create_valid_data(self):
        """Helper to create valid test data"""
        dates = pd.date_range('2023-01-01', '2023-01-31', freq='D')
        return pd.DataFrame({
            'date': dates,
            'open': [100 + i for i in range(len(dates))],
            'high': [105 + i for i in range(len(dates))],
            'low': [95 + i for i in range(len(dates))],
            'close': [102 + i for i in range(len(dates))],
            'volume': [1000000 + i * 10000 for i in range(len(dates))]
        })
    
    def test_valid_data(self):
        """Test validation of valid data"""
        df = self.create_valid_data()
        report = validate_ohlcv_data(df, ticker='AAPL')
        
        assert report.is_valid is True
        assert len(report.critical_issues) == 0
        assert report.stats['quality_score'] > 90
    
    def test_missing_columns(self):
        """Test data with missing columns"""
        df = pd.DataFrame({
            'date': ['2023-01-01'],
            'close': [100]
        })
        
        report = validate_ohlcv_data(df, ticker='AAPL')
        assert report.is_valid is False
        assert any('Missing required columns' in issue for issue in report.critical_issues)
    
    def test_empty_dataframe(self):
        """Test empty dataframe"""
        df = pd.DataFrame()
        report = validate_ohlcv_data(df, ticker='AAPL')
        
        assert report.is_valid is False
        assert any('DataFrame is empty' in issue for issue in report.critical_issues)
    
    def test_null_values(self):
        """Test data with null values"""
        df = self.create_valid_data()
        df.loc[5, 'close'] = None
        df.loc[10, 'volume'] = None
        
        report = validate_ohlcv_data(df, ticker='AAPL')
        assert any('null values' in issue.lower() for issue in report.critical_issues)
    
    def test_negative_prices(self):
        """Test data with negative prices"""
        df = self.create_valid_data()
        df.loc[5, 'close'] = -100
        
        report = validate_ohlcv_data(df, ticker='AAPL')
        assert any('negative' in issue.lower() for issue in report.critical_issues)
    
    def test_zero_prices(self):
        """Test data with zero prices"""
        df = self.create_valid_data()
        df.loc[5, 'close'] = 0
        
        report = validate_ohlcv_data(df, ticker='AAPL')
        assert any('zero' in issue.lower() for issue in report.critical_issues)
    
    def test_high_low_relationship(self):
        """Test high < low validation"""
        df = self.create_valid_data()
        df.loc[5, 'high'] = 90
        df.loc[5, 'low'] = 110
        
        report = validate_ohlcv_data(df, ticker='AAPL')
        assert any('high < low' in issue.lower() for issue in report.critical_issues)
    
    def test_open_close_outside_range(self):
        """Test open/close outside high-low range"""
        df = self.create_valid_data()
        df.loc[5, 'close'] = 200  # Way above high
        
        report = validate_ohlcv_data(df, ticker='AAPL')
        # Should be flagged in warnings or critical issues
        assert len(report.warnings) > 0 or len(report.critical_issues) > 0
    
    def test_duplicate_dates(self):
        """Test duplicate dates"""
        df = self.create_valid_data()
        # Add duplicate row
        duplicate_row = df.iloc[0:1].copy()
        df = pd.concat([df, duplicate_row], ignore_index=True)
        
        report = validate_ohlcv_data(df, ticker='AAPL')
        has_duplicate_warning = (any('duplicate' in issue.lower() for issue in report.warnings) or 
                                any('duplicate' in issue.lower() for issue in report.critical_issues))
        assert has_duplicate_warning
    
    def test_date_gaps(self):
        """Test detection of date gaps"""
        df = self.create_valid_data()
        # Remove some rows to create gaps
        df = df[df.index < 5].append(df[df.index > 15])
        
        report = validate_ohlcv_data(df, ticker='AAPL', max_date_gap_days=3)
        assert any('gap' in issue.lower() for issue in report.warnings)
    
    def test_extreme_price_changes(self):
        """Test detection of extreme price changes"""
        df = self.create_valid_data()
        df.loc[5, 'close'] = 1000  # Huge jump
        
        report = validate_ohlcv_data(df, ticker='AAPL', max_price_change_pct=10.0)
        assert any('price change' in issue.lower() for issue in report.warnings)
    
    def test_outlier_detection(self):
        """Test outlier detection"""
        df = self.create_valid_data()
        # Add an outlier
        df.loc[5, 'volume'] = 100000000  # Way above normal
        
        report = validate_ohlcv_data(df, ticker='AAPL', enable_outlier_detection=True)
        assert 'outliers_detected' in report.stats
    
    def test_quality_score_calculation(self):
        """Test quality score calculation"""
        df = self.create_valid_data()
        report = validate_ohlcv_data(df, ticker='AAPL')
        
        assert 'quality_score' in report.stats
        assert 0 <= report.stats['quality_score'] <= 100
    
    def test_quality_score_with_issues(self):
        """Test quality score decreases with issues"""
        df_good = self.create_valid_data()
        report_good = validate_ohlcv_data(df_good, ticker='AAPL')
        
        df_bad = self.create_valid_data()
        df_bad.loc[5, 'close'] = None  # Add null
        df_bad.loc[10, 'close'] = -100  # Add negative
        report_bad = validate_ohlcv_data(df_bad, ticker='AAPL')
        
        assert report_bad.stats['quality_score'] < report_good.stats['quality_score']
    
    def test_data_quality_report_structure(self):
        """Test DataQualityReport structure"""
        df = self.create_valid_data()
        report = validate_ohlcv_data(df, ticker='AAPL')
        
        assert hasattr(report, 'ticker')
        assert hasattr(report, 'is_valid')
        assert hasattr(report, 'critical_issues')
        assert hasattr(report, 'warnings')
        assert hasattr(report, 'stats')
        assert hasattr(report, 'record_count')
        assert hasattr(report, 'validation_date')
        
        assert isinstance(report.critical_issues, list)
        assert isinstance(report.warnings, list)
        assert isinstance(report.stats, dict)
    
    def test_stats_content(self):
        """Test stats dictionary content"""
        df = self.create_valid_data()
        report = validate_ohlcv_data(df, ticker='AAPL')
        
        assert 'quality_score' in report.stats
        assert 'null_count' in report.stats
        assert 'date_range' in report.stats
        assert 'price_range' in report.stats


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
