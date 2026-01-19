#!/usr/bin/env python3
"""
Analyze unique categories in each column for creating typed search function.
"""

import pandas as pd
from pathlib import Path
import json

def analyze_categories():
    csv_path = Path('1c_catalog_full_20260118_201417.csv')
    
    print(f"Loading CSV: {csv_path}")
    df = pd.read_csv(csv_path, encoding='utf-8', low_memory=False)
    
    print(f"\nDataset: {len(df)} rows × {len(df.columns)} columns\n")
    print("=" * 80)
    print("UNIQUE CATEGORIES BY COLUMN")
    print("=" * 80)
    
    categories = {}
    
    for col in df.columns:
        # Get non-null, non-empty values
        values = df[col].dropna()
        values = [str(v).strip() for v in values if str(v).strip()]
        unique_vals = sorted(set(values))
        
        categories[col] = {
            'total': len(values),
            'unique_count': len(unique_vals),
            'values': unique_vals
        }
        
        print(f"\n{col}:")
        print(f"  Total non-empty: {len(values)}")
        print(f"  Unique: {len(unique_vals)}")
        
        if len(unique_vals) <= 50:
            print(f"  Values: {unique_vals}")
        else:
            print(f"  First 20: {unique_vals[:20]}")
            print(f"  ... and {len(unique_vals) - 20} more")
    
    # Save to JSON for further use
    output_file = Path('catalog_categories.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)
    
    print(f"\n\nCategories saved to: {output_file}")
    
    return categories

if __name__ == '__main__':
    analyze_categories()
