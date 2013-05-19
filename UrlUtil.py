from urllib.parse import urlparse, urlunparse, urljoin
from urllib.request import urlopen

import os.path
import uuid
import itertools

try:
  from lxml import etree
  #print("running with lxml.etree")
except ImportError:
  try:
    import xml.etree.cElementTree as etree
    #print("running with cElementTree on Python 2.5+")
  except ImportError:
    try:
      import xml.etree.ElementTree as etree
      #print("running with ElementTree on Python 2.5+")
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
    def __init__(self, nodes = None):
        self.elements = []
        self.bases = []
        if nodes is None:
          return
        if isinstance(nodes, list):
          for node in nodes:
              self.append(node)
        else:
          for bnode in nodes.iterWithBased:
            self.append(*bnode)
        
    def find(self, tag):
        for element, base in zip(self.elements, self.bases):
            node = element.find(tag) 
            if  node is not None:
                source = XmlSource()
                source.append(node)
                return source                
        return None
      
    def findNode(self, tag):
        for element in self.elements:
          node = element.find(tag)
          if node is not None:
            return node
    
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
        
    def iterWithBased(self):
      for element, base in zip(self.elements, self.bases):
        for node in element:
          yield node, base
          

def xmlStringLoader(xml):
    nodes = XmlSource()
    root = etree.fromstring(xml)
    nodes.append(root)
    return nodes

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
    
    
