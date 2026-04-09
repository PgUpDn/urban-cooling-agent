#!/usr/bin/env python3
"""
View LLM Interaction Records
"""
import json
import glob
import os

def find_latest():
    files = glob.glob("/scratch/Urban/llm_interactions_*.json")
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]

def main():
    json_file = find_latest()
    if not json_file:
        print("❌ No LLM interaction records found")
        print("💡 Please run first: python full_analysis_with_recording_en.py")
        return
    
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    print("="*80)
    print("🤖 LLM Interaction Records")
    print("="*80)
    print(f"File: {os.path.basename(json_file)}\n")
    
    info = data['session_info']
    print(f"📊 Overall Statistics:")
    print(f"   Total interactions: {info['total_interactions']}")
    print(f"   Total time: {info['total_time']:.2f}s\n")
    
    for i, interaction in enumerate(data['interactions'], 1):
        print(f"{'='*80}")
        print(f"Interaction {i}: {interaction['stage']}")
        print(f"{'='*80}")
        print(f"⏰ Timestamp: {interaction['timestamp']}")
        print(f"⏱️  Duration: {interaction['elapsed_time']:.2f}s")
        print(f"📏 Prompt: {interaction['prompt_length']} characters")
        print(f"📏 Response: {interaction['response_length']} characters\n")
        
        print("📝 Prompt:")
        print("-"*60)
        prompt = interaction['prompt']
        print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        print()
        
        print("💬 Response:")
        print("-"*60)
        response = interaction['response']
        print(response[:500] + "..." if len(response) > 500 else response)
        print("\n")
    
    print("="*80)
    print(f"💾 Full record: {json_file}")
    print("="*80)

if __name__ == "__main__":
    main()

