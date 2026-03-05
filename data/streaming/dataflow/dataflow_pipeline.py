import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
import json
import logging
import argparse

class ParseMessage(beam.DoFn):
    """Parses the JSON message from Pub/Sub."""
    def process(self, element):
        try:
            # Pub/Sub payload is bytes, so decode and parse
            yield json.loads(element.decode('utf-8'))
        except Exception as e:
            logging.error(f"Failed to parse event: {element}. Error: {e}")

def run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--input_topic',
        dest='input_topic',
        required=True,
        help='Input Pub/Sub topic to process.')
    parser.add_argument(
        '--output_table',
        dest='output_table',
        required=True,
        help='Output BigQuery table for results specified as: PROJECT:DATASET.TABLE')
    
    known_args, pipeline_args = parser.parse_known_args(argv)

    # Set up streaming pipeline options
    options = PipelineOptions(pipeline_args)
    options.view_as(StandardOptions).streaming = True

    # Define the BigQuery Table Schema
    table_schema = {
        'fields': [
            {'name': 'event_type', 'type': 'STRING', 'mode': 'NULLABLE'},
            {'name': 'symbol', 'type': 'STRING', 'mode': 'REQUIRED'},
            {'name': 'price', 'type': 'FLOAT', 'mode': 'REQUIRED'},
            {'name': 'quantity', 'type': 'FLOAT', 'mode': 'REQUIRED'},
            {'name': 'timestamp', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'},
        ]
    }

    with beam.Pipeline(options=options) as p:
        # Read from Pub/Sub, parse, and write directly into BigQuery
        (p 
         | 'Read from PubSub' >> beam.io.ReadFromPubSub(topic=known_args.input_topic)
         | 'Parse JSON' >> beam.ParDo(ParseMessage())
         | 'Write to BigQuery' >> beam.io.WriteToBigQuery(
             known_args.output_table,
             schema=table_schema,
             write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
             create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED)
        )

if __name__ == '__main__':
    logging.getLogger().setLevel(logging.INFO)
    # Default CLI run example:
    # python dataflow_pipeline.py --input_topic projects/alti-analytics-prod/topics/live-events --output_table alti-analytics-prod:alti_analytics_prod.live_market_data --runner DataflowRunner --project alti-analytics-prod --region us-central1 --temp_location gs://alti-analytics-dev-vertex-artifacts/temp
    run()
