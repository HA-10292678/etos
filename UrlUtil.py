from urllib.parse import urlparse, urlunparse, urljoin
from urllib.request import urlopen

import os.path
import uuid
import itertools

try:
  from lxml import etree
  print("running with lxml.etree")
except ImportError:
  try:
    # Python 2.5
    import xml.etree.cElementTree as etree
    print("running with cElementTree on Python 2.5+")
  except ImportError:
    try:
      # Python 2.5
      import xml.etree.ElementTree as etree
      print("running with ElementTree on Python 2.5+")
    except ImportError:
      try:
        # normal cElementTree install
        import cElementTree as etree
        print("running with cElementTree")
      except ImportError:
        try:
          # normal ElementTree install
          import elementtree.ElementTree as etree
          print("running with ElementTree")
        except ImportError:
          print("Failed to import ElementTree from any known place")


def common(s):
    pivot = s[0]
    if len(s) == 1:
        return pivot
    assert all(pivot == element for element in s[1:])
    return pivot


class XmlSource:
    """
        Auxiliary class for representation of XML contexts which are diversified to several
        elements, possibly to several XML documents.
        The object provide minimal API of xml.etree.ElementTree.Element objects (find and iterator)
    """
    def __init__(self, nodes = []):
        self.elements = []
        self.bases = []
        for node in nodes:
            self.append(node)
        
    def find(self, tag):
        for element in self.elements:
            if element.find(tag) is not None:
                return element.find(tag)
        return None
    
    @property
    def commonId(self):
        ids = [element.get("id", None) for element in self.elements
                 if element.get("id", None) is not None]
        if not ids:
            return uuid.uuid4() 
        return common(ids)
        
    @property
    def commonTag(self):
        tags = [element.tag for element in self.elements]
        return common(tags)
    
    
    def get(self, key, default = None):
        for element in self.elements:
            if element.get(key, None) is not None:
                return element.get(key)
        return default
    
    def getWithBase(self, key, default = None):
        for element, base in zip(self.elements, self.bases):
            if element.get(key, None) is not None:
                return (element.get(key), base)
        return (default, None)
        
    def append(self, node, base = None):
        if isinstance(node, XmlSource):
            self.elements.extend(node.elements)
        else:
            self.elements.append(node)
        self.bases.append(base)
    
    def __str__(self):
        return ",".join(str(element) for element in self.elements)
    
    def __iter__(self):
        return itertools.chain(*self.elements)


def xmlLoader(*args, base=None):
    urls =  []
    for url in args:
        urls.extend(url.split("|"))
    nodes = XmlSource()
    for url in urls:
        pu = urlparse(url) if base is None else urlparse(urljoin(base, url))
        scheme = pu.scheme
        path = pu.path
        if scheme == "":
            scheme = "file"
            if not os.path.isabs(path):
                path = os.path.abspath(path)
        
        target = urlunparse((scheme, pu.netloc, path, pu.params, pu.query, ""))
        data = urlopen(target)
        root = etree.parse(data)
        if pu.fragment == "":
            node = root.getroot()
        else:
            node = root.getroot().find(pu.fragment)
        nodes.append(node, base=target)

    return nodes        
    
    
