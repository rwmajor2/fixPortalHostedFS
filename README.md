# fixPortalHostedFS
Python script that attempts to fix Hosted Feature Services when a Portal has become unfederated

# Dependencies
This script must be run on the Portal server so it can have access to \arcgisportal.

This script requires Esri's Python API for ArcGIS to be installed on the Portal server with Python 3.

It's best that a Portal full reindex occur before running this script and is required after running this script.  It has been found that when the Hosting site has become unfederated and then federated back to Portal, some of the indexing is not updated properly.
