"""
CLI for Anomaly Detection - Train, Serve, Score
"""
import click
import pandas as pd
import uvicorn
from pathlib import Path
from .model import AnomalyDetector


@click.group()
def cli():
    """Anomaly Detection CLI"""
    pass


@cli.command()
@click.option('--data', required=True, help='Path to training CSV file')
@click.option('--output', default='model.pkl', help='Output model file')
@click.option('--threshold-percentile', default=90, help='Threshold percentile (default: 90)')
def train(data, output, threshold_percentile):
    """
    Train anomaly detection model
    
    Example:
        anomaly-detector train --data logs.csv --output model.pkl
    """
    click.echo(f" Loading training data from {data}...")
    
    # Load data
    df = pd.read_csv(data)
    required_cols = ['message', 'namespace', 'pod']
    
    if not all(col in df.columns for col in required_cols):
        click.echo(f" Error: CSV must have columns: {required_cols}", err=True)
        return
    
    click.echo(f"   Loaded {len(df):,} log entries")
    
    # Train
    detector = AnomalyDetector(threshold_percentile=threshold_percentile)
    detector.train(df)
    
    # Save
    detector.save(output)
    click.echo(f" Model saved to {output}")


@cli.command()
@click.option('--model', default='model.pkl', help='Model file')
@click.option('--port', default=8080, help='Port to serve on')
@click.option('--host', default='0.0.0.0', help='Host to bind to')
def serve(model, port, host):
    """
    Start anomaly detection service
    
    Example:
        anomaly-detector serve --model model.pkl --port 8080
    """
    click.echo(f"Starting service on {host}:{port}...")
    click.echo(f"   Model: {model}")
    click.echo(f"   Endpoints:")
    click.echo(f"     POST http://localhost:{port}/predict")
    click.echo(f"     GET  http://localhost:{port}/metrics")
    
    uvicorn.run(
        "src.service:app",
        host=host,
        port=port,
        reload=False
    )


@cli.command()
@click.option('--model', default='model.pkl', help='Model file')
@click.option('--file', required=True, help='File with logs to score (CSV or JSONL)')
@click.option('--output', default='predictions.csv', help='Output file')
def score(model, file, output):
    """
    Score logs from file
    
    Example:
        anomaly-detector score --model model.pkl --file test.csv
    """
    click.echo(f" Loading model from {model}...")
    detector = AnomalyDetector.load(model)
    
    click.echo(f" Loading logs from {file}...")
    
    # Load logs
    if file.endswith('.csv'):
        df = pd.read_csv(file)
    elif file.endswith('.jsonl'):
        df = pd.read_json(file, lines=True)
    else:
        click.echo(" Error: File must be CSV or JSONL", err=True)
        return
    
    click.echo(f"   Loaded {len(df):,} log entries")
    click.echo(f" Scoring...")
    
    # Score each log
    predictions = []
    for idx, row in df.iterrows():
        log_entry = {
            'message': row['message'],
            'namespace': row['namespace'],
            'pod': row['pod']
        }
        result = detector.predict(log_entry)
        predictions.append(result)
    
    # Save results
    results_df = pd.DataFrame(predictions)
    results_df = pd.concat([df, results_df], axis=1)
    results_df.to_csv(output, index=False)
    
    n_anomalies = results_df['is_anomaly'].sum()
    click.echo(f" Scored {len(df):,} logs")
    click.echo(f"   Anomalies detected: {n_anomalies:,} ({n_anomalies/len(df)*100:.2f}%)")
    click.echo(f"   Results saved to {output}")


@cli.command()
@click.option('--model', default='model.pkl', help='Model file')
def info(model):
    """Show model information"""
    click.echo(f" Loading model from {model}...")
    detector = AnomalyDetector.load(model)
    
    click.echo(f"\n Model Information:")
    click.echo(f"   Threshold: {detector.threshold:.2f}")
    click.echo(f"   Percentile: {detector.threshold_percentile}%")
    click.echo(f"   ISO Forest estimators: {detector.iso_forest.n_estimators}")


if __name__ == '__main__':
    cli()
