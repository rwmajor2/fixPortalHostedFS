# fixPortalHostedFS
Python script that attempts to fix Hosted Feature Services when a Portal's Hosting ArcGIS Server site has become unhosted and/or unfederated.  When a Portal loses its federation with the Hosting ArcGIS Server site (either intentionally, unintentionally, or in troubleshooting), Hosted Feature Services lose its knowledge as a "Hosted Service" (typeKeyword).

Also, when the site is federated back with Portal, new items get created for all of the site's Services and the original HFS items owned by users become orphaned from the corresponding ArcGIS Server services due to the following properties associated with a service:

 "portalProperties": {
  "isHosted": false,
  "portalItems": [{
   "itemID": "2f3f8e5e6d5940ba949a8af4b2862364",
   "type": "FeatureServer"
  }]
 },

This script attempts to find original HFS items, fix the AGS Service JSON above, and then update the Portal item's iteminfo.xml file to re-establish the proper relationships.

Additionally, as changes are made to the iteminfo.xml files, the script allows for a backup directory to be specified where the original iteminfo.xml files will be copied to preserve their original content in the event this needs to be rolled back.

# Dependencies
This script must be run on the Portal server so it can have access to \arcgisportal content store (required to update the iteminfo.xml files).

This script requires Esri's Python API for ArcGIS to be installed on the Portal server with Python 3.

It's best that a Portal full reindex occurs <b>before</b> running this script and is required <b>after</b> running this script.  It has been found that when the Hosting site has become unfederated and then federated back to Portal, some of the indexing is not updated properly.  Also, after running this script, a reindex is required to refresh its index from the changes to the iteminfo.xml changes.
