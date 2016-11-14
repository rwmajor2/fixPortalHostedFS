import ssl, sys, getopt, getpass, time, re, os
import logging, json, subprocess

# This script is specifically tested with Python 3.5 that
#   utilizes the Python API for WebGIS
from urllib.error import URLError
from urllib.parse import urlencode
import urllib.request

from xml.dom.minidom import parse, parseString  # Used to edit itemInfo.xml files for items

from arcgis.gis import *
from shutil import copyfile

def gethostingserver(gis):
    """
    Finds the Hosting Server associated with Portal and gets the public URL.
    The assumption is that we are trying to fix Hosted Features Services
    that are associated with this URL.

    Input
        gis - Python API connection object
    Output:
        string of the Hosting server public URL (not admin URL); if not found, None
    """

    request_url = gis._url + "/sharing/rest/portals/" + gis.properties.id + "/servers"
    print(request_url)
    ret = gis._con.get(request_url)
    for server in ret['servers']:
        if server['serverRole'] == 'HOSTING_SERVER' and server['isHosted']:
            return server['url']
    return None


def openurl(url,params = None):
    """
    Makes a manual REST call to a URL with params.  We are using this for any
    REST calls not currently supported by the Python API for ArcGIS.

    Input
        url
        params - JSON object of parameters to use
    Output:
        JSON response
    """

    url_params = {"f": "pjson"}
    if params:
        params.update(url_params)
    else:
        params = url_params
    encoded_params = urlencode(params)
    bd = encoded_params.encode('utf-8')
    req = urllib.request.Request(url, bd)
    resp = urllib.request.urlopen(req)
    data = resp.read()
    url_json = json.loads(data.decode('utf-8'))
    return url_json


def updateitem(serviceAdminURL, token, serviceJSON):
    """
    Update an ArcGIS Server service definition for a Feature Service
    using the Admin API, which currently isn't supported in Python API for ArcGIS
       e.g. https://<server>:6443/arcgis/admin

    Input
        serviceAdminURL - ArcGIS Server Admin API url
        token - token for connecting to the ArcGIS Server
        serviceJSON - full JSON service properties
    Output:
        JSON response
    """

    editServiceInfoURL = '{0}/edit'.format(serviceAdminURL)
    params = dict(token=token, service=json.dumps(serviceJSON))
    edit_request = openurl(editServiceInfoURL,params)
    return edit_request


# Defines the entry point into the script
def main(argv):

    # Connect using internal port as a Portal Admin that did the most recent federation
    portalurl = 'https://wdctyint000044.esri.com:7443/arcgis'
    adminUsername = 'portaladmin'
    adminPassword = 'esri.agp'
    itemsfolder = r'C:\arcgisportal\content\items'
    federation_user = 'portaladmin'
    backuploc = r'C:\arcgisportal_fix_bkup'

    # Temporary change Geosaurus logging level to prevent messages from its module
    curloglevel = logging.getLogger("arcgis").getEffectiveLevel()
    logging.getLogger("arcgis").setLevel(logging.CRITICAL)
    try:
        portal = GIS(portalurl, adminUsername, adminPassword, verify_cert=False)
    except URLError as e:
        sys.exit("Invalid Portal URL...")
    except RuntimeError as e2:
        sys.exit("Invalid Portal username and password...")

    # Change Geosaurus logging level back to default value
    logging.getLogger("arcgis").setLevel(curloglevel)

    # First, let's make sure this Portal is capable of Hosted Feature Services
    props = portal.properties

    # Check to see Portal supports Hosted Feature Services to begin with.
    #  If not, exit because there is no need to fix HFS if it doesn't support it
    if not props['supportsHostedServices']:
        sys.exit("This Portal does not currently support hosting services.")

    # Get the current Hosting Server URL of Portal; we are going to make sure this matches
    #   as we fix items.
    hostingurl = gethostingserver(portal).lower()
    if hostingurl is None:
        sys.exit("This portal does not have a Hosting Server currently associated with it.")

    hostingurl += "/rest/services/hosted/"
    print("Hosting URL is {}\n".format(hostingurl))

    # Stub out the backup location
    path = os.path.join(backuploc, "content", "items")
    if not os.path.isdir(path):
        try:
            os.makedirs(path)
        except OSError:
            if not os.path.isdir(path):
                sys.exit("Unable to create full path to backup location for files:  {}".format(path))

    # Find all items in the Portal that are of type Feature Service and not owned by a particular user.
    #   The basic assumption here is that this particular user owns all of the Feature Services after a
    #   refederation and we don't want to deal with these items.
    items = portal.content.search('NOT owner:{}'.format(federation_user), item_type='Feature Service', max_items=1000)

    olditemids = []
    for item in items:
        # Check to see if Hosted is in the URL and it currently does NOT contain "Hosted Service" as a type keyword.
        #   We make a basic assumption that these are items we need to fix.
        if (hostingurl in item.url.lower()) and (not("Hosted Service" in item['typeKeywords'])):
            # update the JSON service definition to ArcGIS Server
            query_url = item.url.replace("/rest", "/admin").replace("/FeatureServer", ".FeatureServer")
            ret = openurl(query_url, params = {"f": "pjson", "token": portal._con.token})

            # Check to see if the Hosted Service URL exists.  If not, this might be an orphaned Portal item
            #   at this point and skip the rest of the for loop and move on to next item.
            if 'code' in ret:
                if ret['code'] == 404:
                    continue

            print(ret['portalProperties'])

            # First, if the Hosting flag is false, let's update it.
            if ret['portalProperties']['isHosted'] == False:
                print("Fixing {}".format(item.url))
                ret['portalProperties']['isHosted'] = True
                print(updateitem(query_url, portal._con.token, ret))

            # Next, see if the associate Service itemId matches this Portal item.  If not, then update
            #   to match and update the underlying XML file.
            if ret['portalProperties']['portalItems'][0]['itemID'] != item.id:
                # Before we overwrite, keep track of the old itemId owned by someone else that we can
                #  delete and clean up
                olditemids.append(ret['portalProperties']['portalItems'][0]['itemID'])

                # Update itemId
                ret['portalProperties']['portalItems'][0]['itemID'] = item.id

                print(ret['portalProperties'])
                print("="*60)
                print(updateitem(query_url,portal._con.token, ret))

                # update the Portal item XML file on disk
                iteminfo_path = os.path.join(itemsfolder, item.id, "esriinfo", "iteminfo.xml")
                doc = parse(iteminfo_path)
                typekeywords = doc.getElementsByTagName('typekeywords')[0]
                keywords = typekeywords.getElementsByTagName("typekeyword")
                kw = []
                for keyw in keywords:
                    kw.append(str(keyw.firstChild.data))

                # If the 'Hosted Service' typekeyword isn't found, then make a copy of the itemInfo.xml file
                #   to the backup location, then add the XML tag to the itemInfo.xml file.
                #
                # When this script is complete, you need to do a Reindex on Portal for it to pick up the
                #   new keyword in this XML file.
                if not 'Hosted Service' in kw:
                    # Create a backup of the file
                    bk = os.path.join(backuploc, "content", "items", item.id, "esriinfo")
                    os.makedirs(bk)
                    copyfile(iteminfo_path, os.path.join(bk, "iteminfo.xml"))

                    x = doc.createElement("typekeyword")
                    txt = doc.createTextNode("Hosted Service")
                    x.appendChild(txt)
                    typekeywords.appendChild(x)
                    file_handle = open(iteminfo_path, "w")
                    doc.writexml(file_handle)
                    file_handle.close()

    # Once we are all done; go delete the old itemsIds in the Portal since they are now orphaned.
    #   Only delete if the federation portal admin owns the item.
    for id in olditemids:
        item = portal.content.get(id)
        if item.owner == federation_user:
            success = item.delete()
            if success:
                print("Old item {} delete...".format(id))

    # successful script execution return
    return 0

# Script start
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

