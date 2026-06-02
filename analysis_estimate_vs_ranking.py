#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Analysis: Compare expert ranking derived from estimates vs. actual ranking data

This script:
1. Extracts each expert's technique effectiveness estimates
2. Derives a ranking from those estimates (highest estimate = rank 1)
3. Loads the actual expert rankings 
4. Compares the two rankings per expert per failure mode
5. Calculates consistency metrics (Kendall's tau, rank correlation)
"""

import json
import csv
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple
import statistics

def load_detailed_estimates(csv_path: str) -> Dict:
    """Load estimates from detailed_estimates.csv"""
    estimates_by_expert = defaultdict(lambda: defaultdict(dict))
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            expert = row['expert']
            technique = row['technique_ids']
            failure_mode = row['failure_mode_id']
            estimate = float(row['estimate'])
            
            # Group by expert -> failure_mode -> technique
            estimates_by_expert[expert][failure_mode][technique] = estimate
    
    return estimates_by_expert

def load_rankings(json_path: str) -> Dict:
    """Load rankings from full_results.json"""
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    rankings_by_expert = defaultdict(lambda: defaultdict(dict))
    
    # Navigate to phase2_results or wherever rankings are stored
    if 'phase2_results' in data:
        phase_data = data['phase2_results']
    else:
        print("Warning: No phase2_results found in JSON. Checking for ranking data elsewhere...")
        return {}
    
    for technique_data in phase_data:
        if 'ranking_results' in technique_data:
            for failure_mode_data in technique_data['ranking_results']:
                failure_mode_id = failure_mode_data.get('failure_mode_id', 'unknown')
                for round_data in failure_mode_data.get('rounds_data', []):
                    for response in round_data.get('responses', []):
                        expert = response.get('expert', 'unknown')
                        ranking_json = response.get('ranking_json', [])
                        
                        # Store ranking data
                        if ranking_json:
                            for item in ranking_json:
                                tech_id = item.get('technique_id')
                                rank = item.get('rank')
                                reduction = item.get('reduction_pct')
                                rankings_by_expert[expert][failure_mode_id][tech_id] = {
                                    'rank': rank,
                                    'reduction_pct': reduction
                                }
    
    return rankings_by_expert

def derive_ranking_from_estimates(estimates: Dict[str, float]) -> Dict[str, int]:
    """
    Convert estimates to ranks (highest estimate = rank 1)
    Returns dict of technique -> rank
    """
    # Sort by estimate descending
    sorted_techniques = sorted(estimates.items(), key=lambda x: x[1], reverse=True)
    
    ranking = {}
    for rank, (technique, estimate) in enumerate(sorted_techniques, 1):
        ranking[technique] = rank
    
    return ranking

def calculate_kendall_tau(rank1: Dict[str, int], rank2: Dict[str, int]) -> float:
    """
    Calculate Kendall's tau correlation between two rankings
    Returns value between -1 and 1
    """
    techniques = set(rank1.keys()) & set(rank2.keys())
    
    if len(techniques) < 2:
        return None
    
    # Count concordant and discordant pairs
    concordant = 0
    discordant = 0
    
    techniques_list = sorted(techniques)
    for i, t1 in enumerate(techniques_list):
        for t2 in techniques_list[i+1:]:
            r1_pair = (rank1[t1] - rank1[t2]) * (rank2[t1] - rank2[t2])
            if r1_pair > 0:
                concordant += 1
            elif r1_pair < 0:
                discordant += 1
    
    total_pairs = concordant + discordant
    if total_pairs == 0:
        return None
    
    tau = (concordant - discordant) / total_pairs
    return tau

def analyze_consistency(estimates_data: Dict, rankings_data: Dict) -> Tuple[List[Dict], Dict]:
    """
    Compare estimate-derived rankings vs actual rankings
    Returns detailed results and summary
    """
    results = []
    summary_stats = defaultdict(list)
    
    for expert in estimates_data:
        for failure_mode in estimates_data[expert]:
            estimates = estimates_data[expert][failure_mode]
            
            # Derive ranking from estimates
            derived_ranking = derive_ranking_from_estimates(estimates)
            
            # Get actual ranking if available
            if expert in rankings_data and failure_mode in rankings_data[expert]:
                actual_ranking = {}
                for tech_id, rank_data in rankings_data[expert][failure_mode].items():
                    actual_ranking[tech_id] = rank_data['rank']
                
                # Calculate correlation
                tau = calculate_kendall_tau(derived_ranking, actual_ranking)
                
                # Build detailed result
                detail_row = {
                    'expert': expert,
                    'failure_mode': failure_mode,
                    'kendall_tau': tau,
                    'derived_ranking': derived_ranking,
                    'actual_ranking': actual_ranking,
                    'estimates': estimates,
                    'estimate_values': list(estimates.values()),
                }
                
                # Detailed technique comparison
                all_techniques = set(derived_ranking.keys()) | set(actual_ranking.keys())
                technique_details = []
                for tech in sorted(all_techniques):
                    derived_rank = derived_ranking.get(tech, '—')
                    actual_rank = actual_ranking.get(tech, '—')
                    estimate_val = estimates.get(tech, None)
                    
                    rank_match = "✓" if derived_rank == actual_rank else "✗"
                    
                    technique_details.append({
                        'technique': tech,
                        'estimate': estimate_val,
                        'derived_rank': derived_rank,
                        'actual_rank': actual_rank,
                        'match': rank_match,
                    })
                
                detail_row['technique_details'] = technique_details
                results.append(detail_row)
                
                if tau is not None:
                    summary_stats['kendall_tau_values'].append(tau)
                    summary_stats['kendall_tau_by_failure_mode'][failure_mode].append(tau)
    
    return results, dict(summary_stats)

def print_summary(summary_stats: Dict):
    """Print summary statistics"""
    print("\n" + "="*80)
    print("RANKING CONSISTENCY SUMMARY")
    print("="*80)
    
    if 'kendall_tau_values' in summary_stats and summary_stats['kendall_tau_values']:
        tau_values = summary_stats['kendall_tau_values']
        print(f"\nKendall's Tau (correlation between estimate-derived and actual rankings):")
        print(f"  Mean: {statistics.mean(tau_values):.3f}")
        print(f"  Median: {statistics.median(tau_values):.3f}")
        print(f"  Std Dev: {statistics.stdev(tau_values) if len(tau_values) > 1 else 'N/A':.3f}")
        print(f"  Min: {min(tau_values):.3f}")
        print(f"  Max: {max(tau_values):.3f}")
        print(f"  Total comparisons: {len(tau_values)}")
        
        # Perfect consistency = tau close to 1
        perfect = sum(1 for t in tau_values if t > 0.9)
        high = sum(1 for t in tau_values if 0.7 <= t <= 0.9)
        moderate = sum(1 for t in tau_values if 0.3 < t < 0.7)
        low = sum(1 for t in tau_values if t <= 0.3)
        
        print(f"\n  Distribution:")
        print(f"    Perfect agreement (τ > 0.9): {perfect}/{len(tau_values)}")
        print(f"    High agreement (0.7 ≤ τ ≤ 0.9): {high}/{len(tau_values)}")
        print(f"    Moderate agreement (0.3 < τ < 0.7): {moderate}/{len(tau_values)}")
        print(f"    Low/negative agreement (τ ≤ 0.3): {low}/{len(tau_values)}")

def print_detailed_results(results: List[Dict]):
    """Print detailed per-expert rankings"""
    print("\n" + "="*80)
    print("DETAILED EXPERT RANKINGS")
    print("="*80)
    
    for result in results:
        expert = result['expert']
        failure_mode = result['failure_mode']
        tau = result['kendall_tau']
        
        print(f"\n{expert}")
        print(f"  Failure Mode: {failure_mode}")
        print(f"  Kendall's τ: {tau:.3f}" if tau else "  Kendall's τ: N/A")
        print(f"  {'Technique':<35} {'Estimate':>10} {'Derived':>10} {'Actual':>10} {'Match':>8}")
        print(f"  {'-'*35} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")
        
        for tech_detail in result['technique_details']:
            tech = tech_detail['technique']
            est = tech_detail['estimate']
            derived = tech_detail['derived_rank']
            actual = tech_detail['actual_rank']
            match = tech_detail['match']
            
            est_str = f"{est:.1f}" if est is not None else "—"
            derived_str = f"{derived}" if derived != '—' else "—"
            actual_str = f"{actual}" if actual != '—' else "—"
            
            print(f"  {tech:<35} {est_str:>10} {derived_str:>10} {actual_str:>10} {match:>8}")

def main():
    # Get the most recent run
    runs_dir = Path("output_data/runs")
    runs = sorted([d for d in runs_dir.iterdir() if d.is_dir()], reverse=True)
    
    if not runs:
        print("No runs found in output_data/runs/")
        return
    
    latest_run = runs[0]
    print(f"Analyzing run: {latest_run.name}")
    
    csv_file = latest_run / "detailed_estimates.csv"
    json_file = latest_run / "full_results.json"
    
    if not csv_file.exists():
        print(f"Error: {csv_file} not found")
        return
    
    if not json_file.exists():
        print(f"Error: {json_file} not found")
        return
    
    # Load data
    print("\nLoading data...")
    estimates_data = load_detailed_estimates(str(csv_file))
    rankings_data = load_rankings(str(json_file))
    
    if not rankings_data:
        print("Warning: No ranking data found in JSON file")
        print("The analysis requires both estimates AND ranking data.")
        print("Please ensure the run was configured with 'run_technique_ranking: true'")
        return
    
    # Analyze
    print("Analyzing consistency between estimate-derived and actual rankings...")
    results, summary_stats = analyze_consistency(estimates_data, rankings_data)
    
    # Output
    print_summary(summary_stats)
    print_detailed_results(results)
    
    # Save to file
    output_file = latest_run / "ranking_consistency_analysis.json"
    with open(output_file, 'w') as f:
        json.dump({
            'summary_stats': summary_stats,
            'detailed_results': [
                {
                    'expert': r['expert'],
                    'failure_mode': r['failure_mode'],
                    'kendall_tau': r['kendall_tau'],
                    'technique_details': r['technique_details'],
                } for r in results
            ]
        }, f, indent=2)
    
    print(f"\n✓ Analysis saved to: {output_file}")

if __name__ == "__main__":
    main()
