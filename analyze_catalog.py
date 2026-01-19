#!/usr/bin/env python3
"""
Comprehensive analysis of 1C product catalog CSV for BM25 indexing preparation.
Analyzes empty fields, unique values, column meanings, and data quality.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from collections import Counter
import re

def clean_value(val):
    """Clean and normalize values for analysis."""
    if pd.isna(val) or val == '' or str(val).strip() == '':
        return None
    val_str = str(val).strip()
    # Remove extra spaces
    val_str = re.sub(r'\s+', ' ', val_str)
    return val_str if val_str else None

def analyze_column(df, col_name):
    """Comprehensive analysis of a single column."""
    col_data = df[col_name]
    
    # Basic stats
    total = len(col_data)
    non_null = col_data.notna().sum()
    null_count = total - non_null
    null_pct = (null_count / total) * 100
    
    # Clean values for analysis
    clean_values = [clean_value(v) for v in col_data]
    non_empty = [v for v in clean_values if v is not None]
    empty_count = len(clean_values) - len(non_empty)
    
    # Unique values
    unique_values = set(non_empty)
    unique_count = len(unique_values)
    
    # Value distribution
    value_counts = Counter(non_empty)
    top_values = value_counts.most_common(20)
    
    # Data type analysis
    dtype = str(col_data.dtype)
    
    # Sample values
    sample_values = list(unique_values)[:10] if unique_count <= 10 else list(unique_values)[:5]
    
    # Check for patterns
    numeric_pattern = False
    if non_empty:
        try:
            # Try to parse as numeric
            numeric_vals = [float(str(v).replace(',', '.').replace(' ', '')) for v in non_empty[:100]]
            numeric_pattern = True
        except:
            pass
    
    return {
        'column_name': col_name,
        'total_rows': total,
        'non_null_count': non_null,
        'null_count': null_count,
        'null_percentage': round(null_pct, 2),
        'empty_count': empty_count,
        'empty_percentage': round((empty_count / total) * 100, 2),
        'unique_count': unique_count,
        'unique_percentage': round((unique_count / len(non_empty)) * 100, 2) if non_empty else 0,
        'dtype': dtype,
        'is_numeric': numeric_pattern,
        'top_values': top_values,
        'sample_values': sample_values,
        'all_unique_values': sorted(list(unique_values)) if unique_count <= 50 else None
    }

def analyze_empty_conditions(df):
    """Analyze conditions when fields are empty."""
    conditions = {}
    
    for col in df.columns:
        empty_mask = df[col].isna() | (df[col].astype(str).str.strip() == '')
        
        if empty_mask.sum() > 0:
            # Analyze what other fields are present when this one is empty
            empty_rows = df[empty_mask]
            non_empty_rows = df[~empty_mask]
            
            # Check correlation with other fields
            correlations = {}
            for other_col in df.columns:
                if other_col != col:
                    # Percentage of empty rows that have this other field filled
                    empty_with_other = empty_rows[other_col].notna().sum() / len(empty_rows) * 100
                    non_empty_with_other = non_empty_rows[other_col].notna().sum() / len(non_empty_rows) * 100
                    
                    if abs(empty_with_other - non_empty_with_other) > 10:  # Significant difference
                        correlations[other_col] = {
                            'when_empty': round(empty_with_other, 2),
                            'when_filled': round(non_empty_with_other, 2),
                            'difference': round(abs(empty_with_other - non_empty_with_other), 2)
                        }
            
            conditions[col] = {
                'empty_count': empty_mask.sum(),
                'empty_percentage': round(empty_mask.sum() / len(df) * 100, 2),
                'correlations': correlations,
                'sample_empty_rows': empty_rows.head(5).to_dict('records') if len(empty_rows) > 0 else []
            }
    
    return conditions

def infer_column_meaning(col_name, sample_values, unique_count):
    """Infer the meaning of a column based on name and values."""
    col_lower = col_name.lower()
    
    # Direct translations
    translations = {
        'group_name': 'Product group/category name',
        'group_code': 'Product group code (1C identifier)',
        'item_code': 'Product item code (1C identifier)',
        'item_name': 'Product item name (short)',
        'наименование': 'Product name (full Russian)',
        'наименованиедлясайта': 'Product name for website',
        'цена': 'Price (in rubles)',
        'остаток': 'Stock/Inventory quantity',
        'видпиломатериала': 'Type of lumber/wood material',
        'порода': 'Wood species (хвоя/pine, липа/linden, etc.)',
        'сорт': 'Grade/Quality class (A, B, C, AB, etc.)',
        'толщина': 'Thickness (mm)',
        'ширина': 'Width (mm)',
        'длина': 'Length (mm)',
        'влажность': 'Moisture content',
        'типобработки': 'Treatment type (строганый/planed, etc.)',
        'срокпроизводстваднобщие': 'Production time in days',
        'популярностьобщие': 'Popularity score',
        'дополнительнаяедизмерения1': 'Additional unit of measurement 1',
        'дополнительнаяедизмерения2': 'Additional unit of measurement 2',
        'дополнительнаяедизмерения3общие': 'Additional unit of measurement 3',
        'допсвойство': 'Additional property',
        'егаисобщие': 'EGAIS (alcohol tracking system) flag',
        'класс': 'Class',
        'код': 'Code',
        'количествовм2общие': 'Quantity per m²',
        'количествовм3общие': 'Quantity per m³',
        'количествовупаковкеобщие': 'Quantity per package',
        'коэфдополнительнаяедизмерения1': 'Coefficient for additional unit 1',
        'коэфдополнительнаяедизмерения2': 'Coefficient for additional unit 2',
        'коэфдополнительнаяедизмерения3общие': 'Coefficient for additional unit 3',
        'плотностькгм3общие': 'Density (kg/m³)',
        'регионобщие': 'Region',
        'специальныеценыобщие': 'Special prices'
    }
    
    meaning = translations.get(col_name.lower(), 'Unknown field')
    
    # Add insights based on values
    insights = []
    if unique_count == len(sample_values) and len(sample_values) > 0:
        insights.append('High cardinality - likely unique identifier or free text')
    elif unique_count < 10:
        insights.append('Low cardinality - categorical field')
    
    if any('м2' in str(v).lower() or 'м3' in str(v).lower() for v in sample_values[:5]):
        insights.append('Contains measurement units (m², m³)')
    
    return {
        'meaning': meaning,
        'insights': insights
    }

def main():
    csv_path = Path('1c_catalog_full_20260118_201417.csv')
    
    print(f"Loading CSV: {csv_path}")
    print("=" * 80)
    
    # Load CSV
    df = pd.read_csv(csv_path, encoding='utf-8', low_memory=False)
    
    print(f"\nDataset Overview:")
    print(f"  Total rows: {len(df)}")
    print(f"  Total columns: {len(df.columns)}")
    print(f"  Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
    
    print(f"\nColumn Names:")
    for i, col in enumerate(df.columns, 1):
        print(f"  {i:2d}. {col}")
    
    print("\n" + "=" * 80)
    print("ANALYZING EACH COLUMN")
    print("=" * 80)
    
    # Analyze each column
    column_analyses = {}
    for col in df.columns:
        print(f"\nAnalyzing: {col}")
        analysis = analyze_column(df, col)
        column_analyses[col] = analysis
        
        meaning_info = infer_column_meaning(col, analysis['sample_values'], analysis['unique_count'])
        analysis['meaning'] = meaning_info['meaning']
        analysis['insights'] = meaning_info['insights']
        
        print(f"  Meaning: {analysis['meaning']}")
        print(f"  Empty: {analysis['empty_count']} ({analysis['empty_percentage']}%)")
        print(f"  Unique values: {analysis['unique_count']}")
        if analysis['unique_count'] <= 20:
            print(f"  All values: {analysis['all_unique_values']}")
        else:
            print(f"  Top 5 values: {[v[0] for v in analysis['top_values'][:5]]}")
    
    print("\n" + "=" * 80)
    print("ANALYZING EMPTY FIELD CONDITIONS")
    print("=" * 80)
    
    empty_conditions = analyze_empty_conditions(df)
    
    print("\nFields with significant empty values:")
    for col, info in sorted(empty_conditions.items(), key=lambda x: x[1]['empty_count'], reverse=True):
        if info['empty_count'] > 0:
            print(f"\n  {col}:")
            print(f"    Empty: {info['empty_count']} ({info['empty_percentage']}%)")
            if info['correlations']:
                print(f"    Correlations with other fields:")
                for other_col, corr in list(info['correlations'].items())[:3]:
                    print(f"      - {other_col}: {corr['difference']}% difference")
    
    print("\n" + "=" * 80)
    print("DUPLICATE ANALYSIS")
    print("=" * 80)
    
    # Check for duplicate rows
    duplicates = df.duplicated()
    print(f"  Duplicate rows: {duplicates.sum()} ({duplicates.sum() / len(df) * 100:.2f}%)")
    
    # Check for duplicate item codes
    if 'item_code' in df.columns:
        dup_codes = df['item_code'].duplicated()
        print(f"  Duplicate item_code: {dup_codes.sum()}")
        if dup_codes.sum() > 0:
            dup_item_codes = df[df['item_code'].duplicated(keep=False)]['item_code'].unique()[:5]
            print(f"  Sample duplicate codes: {list(dup_item_codes)}")
    
    print("\n" + "=" * 80)
    print("DATA QUALITY SUMMARY")
    print("=" * 80)
    
    # Summary statistics
    summary = {
        'total_rows': len(df),
        'total_columns': len(df.columns),
        'columns_analysis': column_analyses,
        'empty_conditions': empty_conditions,
        'duplicate_rows': int(duplicates.sum()),
        'duplicate_percentage': round(duplicates.sum() / len(df) * 100, 2)
    }
    
    # Save detailed report
    output_file = Path('catalog_analysis_report.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\nDetailed report saved to: {output_file}")
    
    # Create markdown report
    md_report = create_markdown_report(summary)
    md_file = Path('catalog_analysis_report.md')
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(md_report)
    
    print(f"Markdown report saved to: {md_file}")
    
    # Print key findings
    print("\n" + "=" * 80)
    print("KEY FINDINGS FOR BM25 INDEXING")
    print("=" * 80)
    
    # Identify key searchable fields
    key_fields = []
    for col, analysis in column_analyses.items():
        if analysis['empty_percentage'] < 50 and analysis['unique_count'] > 1:
            if any(keyword in col.lower() for keyword in ['name', 'наименование', 'вид', 'порода', 'сорт']):
                key_fields.append({
                    'field': col,
                    'meaning': analysis['meaning'],
                    'completeness': 100 - analysis['empty_percentage'],
                    'cardinality': analysis['unique_count']
                })
    
    print("\nRecommended fields for BM25 indexing:")
    for field in sorted(key_fields, key=lambda x: x['completeness'], reverse=True):
        print(f"  - {field['field']}: {field['meaning']} ({field['completeness']:.1f}% complete, {field['cardinality']} unique values)")

def create_markdown_report(summary):
    """Create a markdown report from analysis."""
    md = []
    md.append("# 1C Product Catalog Analysis Report")
    md.append("")
    md.append(f"**Dataset:** {summary['total_rows']} rows × {summary['total_columns']} columns")
    md.append(f"**Duplicate rows:** {summary['duplicate_rows']} ({summary['duplicate_percentage']}%)")
    md.append("")
    
    md.append("## Column Analysis")
    md.append("")
    md.append("| Column | Meaning | Empty % | Unique | Top Values |")
    md.append("|--------|---------|---------|--------|------------|")
    
    for col, analysis in summary['columns_analysis'].items():
        top_vals = ', '.join([f"{v[0]} ({v[1]})" for v in analysis['top_values'][:3]])
        if len(top_vals) > 50:
            top_vals = top_vals[:47] + "..."
        
        md.append(f"| {col} | {analysis['meaning']} | {analysis['empty_percentage']}% | "
                 f"{analysis['unique_count']} | {top_vals} |")
    
    md.append("")
    md.append("## Empty Field Conditions")
    md.append("")
    
    for col, info in sorted(summary['empty_conditions'].items(), 
                           key=lambda x: x[1]['empty_count'], reverse=True):
        if info['empty_count'] > 0:
            md.append(f"### {col}")
            md.append(f"- Empty: {info['empty_count']} ({info['empty_percentage']}%)")
            if info['correlations']:
                md.append("- Correlations:")
                for other_col, corr in list(info['correlations'].items())[:5]:
                    md.append(f"  - {other_col}: {corr['difference']}% difference")
            md.append("")
    
    md.append("## BM25 Indexing Recommendations")
    md.append("")
    md.append("### High-priority fields (for search):")
    
    searchable_fields = []
    for col, analysis in summary['columns_analysis'].items():
        if analysis['empty_percentage'] < 30:
            if any(kw in col.lower() for kw in ['name', 'наименование', 'вид', 'порода']):
                searchable_fields.append((col, analysis))
    
    for col, analysis in sorted(searchable_fields, key=lambda x: 100 - x[1]['empty_percentage']):
        md.append(f"- **{col}**: {analysis['meaning']}")
        md.append(f"  - Completeness: {100 - analysis['empty_percentage']:.1f}%")
        md.append(f"  - Unique values: {analysis['unique_count']}")
        if analysis['all_unique_values']:
            md.append(f"  - Values: {', '.join(map(str, analysis['all_unique_values'][:10]))}")
        md.append("")
    
    md.append("### Categorical fields (for filtering):")
    
    categorical_fields = []
    for col, analysis in summary['columns_analysis'].items():
        if analysis['unique_count'] < 50 and analysis['unique_count'] > 1:
            if analysis['empty_percentage'] < 50:
                categorical_fields.append((col, analysis))
    
    for col, analysis in sorted(categorical_fields, key=lambda x: x[1]['unique_count']):
        md.append(f"- **{col}**: {analysis['meaning']}")
        md.append(f"  - Unique values: {analysis['unique_count']}")
        if analysis['all_unique_values']:
            md.append(f"  - Values: {', '.join(map(str, analysis['all_unique_values']))}")
        md.append("")
    
    return "\n".join(md)

if __name__ == '__main__':
    main()
