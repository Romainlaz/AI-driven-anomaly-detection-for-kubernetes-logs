"""
Prepare log data from various sources for training
"""
import pandas as pd
import click
from datetime import datetime


@click.group()
def cli():
    """Prepare log data for training"""
    pass


@cli.command()
@click.option('--input', required=True, help='Input CSV file')
@click.option('--output', required=True, help='Output CSV file')
@click.option('--message-col', default='wiremind.message', help='Message column name')
@click.option('--namespace-col', default='kubernetes.namespace_name', help='Namespace column name')
@click.option('--pod-col', default='kubernetes.pod_name', help='Pod column name')
def convert(input, output, message_col, namespace_col, pod_col):
    """
    Convert log CSV to standard format
    
    Standard format:
    - message: Log message text
    - namespace: Kubernetes namespace
    - pod: Pod name
    """
    click.echo(f" Loading {input}...")
    df = pd.read_csv(input)
    
    # Check columns exist
    required = [message_col, namespace_col, pod_col]
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        click.echo(f" Missing columns: {missing}", err=True)
        click.echo(f"   Available: {df.columns.tolist()}")
        return
    
    # Rename to standard format
    df_out = pd.DataFrame({
        'message': df[message_col],
        'namespace': df[namespace_col],
        'pod': df[pod_col]
    })
    
    # Clean
    df_out = df_out.dropna()
    df_out = df_out[df_out['message'].str.len() > 0]
    
    # Save
    df_out.to_csv(output, index=False)
    click.echo(f" Saved {len(df_out):,} logs to {output}")


@cli.command()
@click.option('--input', required=True, multiple=True, help='Input CSV files (multiple)')
@click.option('--output', required=True, help='Output combined CSV')
def combine(input, output):
    """
    Combine multiple CSV files
    
    Example:
        prepare-data combine --input logs.csv --input logs.csv --output combined.csv
    """
    dfs = []
    total = 0
    
    for filepath in input:
        click.echo(f" Loading {filepath}...")
        df = pd.read_csv(filepath)
        dfs.append(df)
        total += len(df)
        click.echo(f"   {len(df):,} logs")
    
    # Combine
    df_combined = pd.concat(dfs, ignore_index=True)
    
    # Deduplicate
    before = len(df_combined)
    df_combined = df_combined.drop_duplicates(subset=['message', 'namespace', 'pod'])
    after = len(df_combined)
    
    # Save
    df_combined.to_csv(output, index=False)
    
    click.echo(f"\n Combined {total:,} → {after:,} logs (removed {before-after:,} duplicates)")
    click.echo(f"   Saved to {output}")


@cli.command()
@click.option('--input', required=True, help='Input CSV')
@click.option('--sample-size', default=1000, help='Sample size')
@click.option('--output', required=True, help='Output sample CSV')
@click.option('--random-seed', default=42, help='Random seed')
def sample(input, sample_size, output, random_seed):
    """
    Create random sample for testing
    """
    click.echo(f" Loading {input}...")
    df = pd.read_csv(input)
    
    # Sample
    if len(df) < sample_size:
        click.echo(f"  Dataset only has {len(df)} rows, using all")
        df_sample = df
    else:
        df_sample = df.sample(n=sample_size, random_state=random_seed)
    
    # Save
    df_sample.to_csv(output, index=False)
    click.echo(f" Saved {len(df_sample):,} logs to {output}")


@cli.command()
@click.option('--input', required=True, help='Input CSV')
def stats(input):
    """
    Show dataset statistics
    """
    click.echo(f" Loading {input}...")
    df = pd.read_csv(input)
    
    click.echo(f"\n Dataset Statistics:")
    click.echo(f"   Total logs: {len(df):,}")
    click.echo(f"   Columns: {df.columns.tolist()}")
    
    if 'message' in df.columns:
        click.echo(f"\n Messages:")
        click.echo(f"   Avg length: {df['message'].str.len().mean():.2f} chars")
        click.echo(f"   Min length: {df['message'].str.len().min()}")
        click.echo(f"   Max length: {df['message'].str.len().max()}")
    
    if 'namespace' in df.columns:
        click.echo(f"\n Namespaces:")
        top_ns = df['namespace'].value_counts().head(5)
        for ns, count in top_ns.items():
            click.echo(f"   {ns}: {count:,} ({count/len(df)*100:.2f}%)")
    
    if 'pod' in df.columns:
        click.echo(f"\n Pods:")
        click.echo(f"   Unique pods: {df['pod'].nunique():,}")
        top_pods = df['pod'].value_counts().head()
        for pod, count in top_pods.items():
            click.echo(f"   {pod}: {count:,}")


if __name__ == '__main__':
    cli()
