# Self-hosted Neo4j Community for OntoMarket, deployed as its own Fly app
# (separate from ontomarket-api) so the database has its own lifecycle,
# volume, and doesn't compete with the API's torch/ML memory footprint.
#
# NEO4J_AUTH is set as a Fly SECRET (fly secrets set), not baked in here —
# credentials never belong in an image layer.

FROM neo4j:5.26-community

# Bolt (application driver connections) + HTTP (browser/health checks).
EXPOSE 7687 7474
