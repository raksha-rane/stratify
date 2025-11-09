"""
Data Validation Module for AQTS Platform

This module provides comprehensive data quality validation for OHLCV (Open, High, Low, Close, Volume) data.
Validates data integrity, detects anomalies, and generates quality reports.

Usage:
    from validators import validate_ohlcv_data
    
    df = yf.download('AAPL', start='2024-01-01', end='2024-12-31')
    report = validate_ohlcv_data(df, ticker='AAPL')
    
    if not report.is_valid:
        raise ValidationError(f"Data quality issues: {report.critical_issues}")
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import json


@dataclass
class DataQualityReport:
    """
    Data quality validation report containing validation results, issues, and statistics.
    
    Attributes:
        ticker: Stock ticker symbol
        validation_date: Timestamp of validation
        is_valid: Overall validation status (True if no critical issues)
        critical_issues: List of critical issues that prevent data usage
        warnings: List of warnings that don't prevent usage but indicate quality concerns
        stats: Dictionary of data statistics and metrics
        record_count: Number of records validated
    """
    ticker: str
    validation_date: datetime = field(default_factory=datetime.now)
    is_valid: bool = True
    critical_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    record_count: int = 0
    
    def add_critical_issue(self, issue: str) -> None:
        """Add a critical issue and mark report as invalid"""
        self.critical_issues.append(issue)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add a warning (doesn't affect validity)"""
        self.warnings.append(warning)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization"""
        return {
            'ticker': self.ticker,
            'validation_date': self.validation_date.isoformat(),
            'is_valid': self.is_valid,
            'critical_issues': self.critical_issues,
            'warnings': self.warnings,
            'stats': self.stats,
            'record_count': self.record_count
        }
    
    def save_to_db(self, session, DataQualityLog) -> None:
        """
        Save validation report to database.
        
        Args:
            session: SQLAlchemy session
            DataQualityLog: SQLAlchemy model class for data_quality_logs table
        """
        try:
            log_entry = DataQualityLog(
                ticker=self.ticker,
                validation_date=self.validation_date,
                is_valid=self.is_valid,
                critical_issues=json.dumps(self.critical_issues),
                warnings=json.dumps(self.warnings),
                stats=json.dumps(self.stats)
            )
            session.add(log_entry)
            session.commit()
        except Exception as e:
            session.rollback()
            raise Exception(f"Failed to save quality report to database: {str(e)}")
    
    def __str__(self) -> str:
        """String representation of the report"""
        status = "✓ VALID" if self.is_valid else "✗ INVALID"
        result = [
            f"Data Quality Report for {self.ticker}",
            f"Status: {status}",
            f"Records: {self.record_count}",
            f"Validation Date: {self.validation_date.strftime('%Y-%m-%d %H:%M:%S')}"
        ]
        
        if self.critical_issues:
            result.append(f"\nCritical Issues ({len(self.critical_issues)}):")
            for issue in self.critical_issues:
                result.append(f"  - {issue}")
        
        if self.warnings:
            result.append(f"\nWarnings ({len(self.warnings)}):")
            for warning in self.warnings:
                result.append(f"  - {warning}")
        
        if self.stats:
            result.append("\nStatistics:")
            for key, value in self.stats.items():
                result.append(f"  {key}: {value}")
        
        return "\n".join(result)


def validate_ohlcv_data(
    df: pd.DataFrame,
    ticker: str = "UNKNOWN",
    max_price_change_pct: float = 50.0,
    max_date_gap_days: int = 5,
    enable_outlier_detection: bool = True
) -> DataQualityReport:
    """
    Validate OHLCV (Open, High, Low, Close, Volume) data quality.
    
    Performs comprehensive validation checks:
    - Null/missing value detection in critical columns
    - Price relationship validation (High >= Low, Open/Close in range)
    - Negative price detection
    - Duplicate date detection
    - Date gap analysis
    - Outlier/anomaly detection
    - Volume validation
    
    Args:
        df: DataFrame with OHLCV data
        ticker: Stock ticker symbol
        max_price_change_pct: Maximum allowed day-over-day price change percentage (default: 50%)
        max_date_gap_days: Maximum allowed gap between trading days (default: 5)
        enable_outlier_detection: Enable statistical outlier detection (default: True)
    
    Returns:
        DataQualityReport object with validation results
    """
    report = DataQualityReport(ticker=ticker)
    
    # Handle empty DataFrame
    if df is None or df.empty:
        report.add_critical_issue("DataFrame is empty or None")
        report.record_count = 0
        return report
    
    report.record_count = len(df)
    
    # Normalize column names to lowercase
    df_normalized = df.copy()
    df_normalized.columns = [col.lower() for col in df_normalized.columns]
    
    # Required columns
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    
    # Check if required columns exist
    missing_cols = [col for col in required_cols if col not in df_normalized.columns]
    if missing_cols:
        report.add_critical_issue(f"Missing required columns: {', '.join(missing_cols)}")
        return report
    
    # ========================================================================
    # VALIDATION CHECK 1: Null/Missing Values
    # ========================================================================
    null_counts = df_normalized[required_cols].isnull().sum()
    total_nulls = null_counts.sum()
    
    if total_nulls > 0:
        for col, count in null_counts.items():
            if count > 0:
                pct = (count / len(df_normalized)) * 100
                if pct > 10:  # More than 10% nulls is critical
                    report.add_critical_issue(f"Column '{col}' has {count} null values ({pct:.1f}%)")
                else:
                    report.add_warning(f"Column '{col}' has {count} null values ({pct:.1f}%)")
    
    report.stats['total_null_values'] = int(total_nulls)
    
    # Remove rows with nulls for further validation
    df_clean = df_normalized.dropna(subset=required_cols)
    clean_record_count = len(df_clean)
    
    if clean_record_count == 0:
        report.add_critical_issue("No valid records after removing nulls")
        return report
    
    report.stats['valid_records'] = clean_record_count
    report.stats['dropped_records'] = report.record_count - clean_record_count
    
    # ========================================================================
    # VALIDATION CHECK 2: High >= Low
    # ========================================================================
    invalid_high_low = df_clean[df_clean['high'] < df_clean['low']]
    if len(invalid_high_low) > 0:
        report.add_critical_issue(
            f"Found {len(invalid_high_low)} records where High < Low"
        )
        report.stats['high_low_violations'] = int(len(invalid_high_low))
    
    # ========================================================================
    # VALIDATION CHECK 3: Open/Close within High-Low range
    # ========================================================================
    invalid_open = df_clean[
        (df_clean['open'] > df_clean['high']) | 
        (df_clean['open'] < df_clean['low'])
    ]
    
    invalid_close = df_clean[
        (df_clean['close'] > df_clean['high']) | 
        (df_clean['close'] < df_clean['low'])
    ]
    
    if len(invalid_open) > 0:
        pct = (len(invalid_open) / clean_record_count) * 100
        if pct > 5:
            report.add_critical_issue(
                f"Found {len(invalid_open)} records where Open is outside High-Low range ({pct:.1f}%)"
            )
        else:
            report.add_warning(
                f"Found {len(invalid_open)} records where Open is outside High-Low range ({pct:.1f}%)"
            )
    
    if len(invalid_close) > 0:
        pct = (len(invalid_close) / clean_record_count) * 100
        if pct > 5:
            report.add_critical_issue(
                f"Found {len(invalid_close)} records where Close is outside High-Low range ({pct:.1f}%)"
            )
        else:
            report.add_warning(
                f"Found {len(invalid_close)} records where Close is outside High-Low range ({pct:.1f}%)"
            )
    
    # ========================================================================
    # VALIDATION CHECK 4: No negative prices
    # ========================================================================
    price_cols = ['open', 'high', 'low', 'close']
    negative_prices = {}
    
    for col in price_cols:
        negative_count = (df_clean[col] < 0).sum()
        if negative_count > 0:
            negative_prices[col] = int(negative_count)
            report.add_critical_issue(
                f"Found {negative_count} negative prices in '{col}' column"
            )
    
    if negative_prices:
        report.stats['negative_prices'] = negative_prices
    
    # Check for zero prices (suspicious but not critical)
    zero_prices = {}
    for col in price_cols:
        zero_count = (df_clean[col] == 0).sum()
        if zero_count > 0:
            zero_prices[col] = int(zero_count)
            report.add_warning(f"Found {zero_count} zero prices in '{col}' column")
    
    if zero_prices:
        report.stats['zero_prices'] = zero_prices
    
    # ========================================================================
    # VALIDATION CHECK 5: Duplicate dates
    # ========================================================================
    if 'date' in df_normalized.columns or isinstance(df_normalized.index, pd.DatetimeIndex):
        if 'date' in df_normalized.columns:
            date_series = df_normalized['date']
        else:
            date_series = df_normalized.index
        
        duplicate_dates = date_series.duplicated()
        duplicate_count = duplicate_dates.sum()
        
        if duplicate_count > 0:
            report.add_critical_issue(
                f"Found {duplicate_count} duplicate dates"
            )
            report.stats['duplicate_dates'] = int(duplicate_count)
    
    # ========================================================================
    # VALIDATION CHECK 6: Date gaps > max_date_gap_days trading days
    # ========================================================================
    if 'date' in df_normalized.columns or isinstance(df_normalized.index, pd.DatetimeIndex):
        try:
            # Ensure we have datetime index
            if 'date' in df_normalized.columns:
                df_sorted = df_clean.sort_values('date')
                dates = pd.to_datetime(df_sorted['date'])
            else:
                df_sorted = df_clean.sort_index()
                dates = df_sorted.index
            
            # Calculate date differences
            date_diffs = dates.diff()
            
            # Find gaps larger than threshold
            large_gaps = date_diffs[date_diffs > pd.Timedelta(days=max_date_gap_days)]
            
            if len(large_gaps) > 0:
                max_gap = date_diffs.max()
                report.add_warning(
                    f"Found {len(large_gaps)} date gaps > {max_date_gap_days} days "
                    f"(max gap: {max_gap.days} days)"
                )
                report.stats['date_gaps'] = {
                    'count': int(len(large_gaps)),
                    'max_gap_days': int(max_gap.days),
                    'avg_gap_days': float(date_diffs.mean().days)
                }
            else:
                report.stats['date_gaps'] = {
                    'count': 0,
                    'max_gap_days': int(date_diffs.max().days) if len(date_diffs) > 0 else 0
                }
        except Exception as e:
            report.add_warning(f"Could not analyze date gaps: {str(e)}")
    
    # ========================================================================
    # VALIDATION CHECK 7: Price change outliers (> max_price_change_pct)
    # ========================================================================
    if enable_outlier_detection and len(df_clean) > 1:
        try:
            df_sorted = df_clean.sort_index() if isinstance(df_clean.index, pd.DatetimeIndex) else df_clean
            
            # Calculate day-over-day price changes
            close_pct_change = df_sorted['close'].pct_change() * 100
            
            # Find extreme price movements
            extreme_changes = close_pct_change[abs(close_pct_change) > max_price_change_pct]
            
            if len(extreme_changes) > 0:
                max_change = abs(close_pct_change).max()
                report.add_warning(
                    f"Found {len(extreme_changes)} price changes > {max_price_change_pct}% "
                    f"(max change: {max_change:.1f}%)"
                )
                report.stats['price_outliers'] = {
                    'count': int(len(extreme_changes)),
                    'max_change_pct': float(max_change),
                    'threshold_pct': max_price_change_pct
                }
            
            # Statistical outlier detection using Z-score
            close_prices = df_sorted['close']
            z_scores = np.abs((close_prices - close_prices.mean()) / close_prices.std())
            statistical_outliers = z_scores[z_scores > 3]
            
            if len(statistical_outliers) > 0:
                report.add_warning(
                    f"Found {len(statistical_outliers)} statistical price outliers (Z-score > 3)"
                )
                report.stats['statistical_outliers'] = int(len(statistical_outliers))
            
        except Exception as e:
            report.add_warning(f"Could not perform outlier detection: {str(e)}")
    
    # ========================================================================
    # VALIDATION CHECK 8: Volume > 0
    # ========================================================================
    zero_volume = (df_clean['volume'] == 0).sum()
    negative_volume = (df_clean['volume'] < 0).sum()
    
    if negative_volume > 0:
        report.add_critical_issue(f"Found {negative_volume} records with negative volume")
        report.stats['negative_volume'] = int(negative_volume)
    
    if zero_volume > 0:
        pct = (zero_volume / clean_record_count) * 100
        if pct > 10:
            report.add_warning(f"Found {zero_volume} records with zero volume ({pct:.1f}%)")
        report.stats['zero_volume'] = int(zero_volume)
    
    # ========================================================================
    # SUMMARY STATISTICS
    # ========================================================================
    try:
        report.stats['price_statistics'] = {
            'close_min': float(df_clean['close'].min()),
            'close_max': float(df_clean['close'].max()),
            'close_mean': float(df_clean['close'].mean()),
            'close_std': float(df_clean['close'].std()),
            'volume_mean': float(df_clean['volume'].mean()),
            'volume_std': float(df_clean['volume'].std())
        }
        
        # Calculate data quality score (0-100)
        quality_score = 100
        
        # Deduct points for issues
        quality_score -= len(report.critical_issues) * 20  # -20 per critical issue
        quality_score -= len(report.warnings) * 5  # -5 per warning
        quality_score = max(0, quality_score)  # Don't go below 0
        
        report.stats['quality_score'] = quality_score
        
    except Exception as e:
        report.add_warning(f"Could not calculate summary statistics: {str(e)}")
    
    return report


def validate_ticker_format(ticker: str) -> bool:
    """
    Validate ticker symbol format.
    
    Args:
        ticker: Stock ticker symbol
    
    Returns:
        True if valid, False otherwise
    """
    if not ticker or not isinstance(ticker, str):
        return False
    
    # Ticker should be alphanumeric, 1-10 characters
    if not ticker.isalnum() or len(ticker) > 10 or len(ticker) < 1:
        return False
    
    return True


def validate_date_range(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Validate date range for data fetching.
    
    Args:
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
    
    Returns:
        Dictionary with 'valid' (bool) and 'error' (str) keys
    """
    try:
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        now = pd.Timestamp.now()
        
        if start > end:
            return {'valid': False, 'error': 'Start date must be before end date'}
        
        if end > now:
            return {'valid': False, 'error': 'End date cannot be in the future'}
        
        # Check if date range is reasonable (not too old, not too long)
        date_range_days = (end - start).days
        
        if date_range_days > 365 * 20:  # More than 20 years
            return {
                'valid': False,
                'error': f'Date range too large: {date_range_days} days (max: {365 * 20})'
            }
        
        if start < pd.Timestamp('1970-01-01'):
            return {'valid': False, 'error': 'Start date too old (before 1970-01-01)'}
        
        return {'valid': True, 'error': None}
        
    except Exception as e:
        return {'valid': False, 'error': f'Invalid date format: {str(e)}'}
