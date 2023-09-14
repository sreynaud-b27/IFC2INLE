# service logging configuration
import logging

logger = logging.getLogger("NSR-BIM")
fh = logging.FileHandler("nsrbim.log", "a")
fmt = logging.Formatter("%(asctime)s::%(funcName)s::%(levelname)-8s::%(message)s", "%Y-%m-%d %H:%M:%S")
fh.setFormatter(fmt)
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)

# configration elements as a python dictionary
main_config = {
    "ifc_iri" : "https://standards.buildingsmart.org/IFC/DEV/IFC2x3/TC1/OWL#",
    "nln_iri" : "http://www.semanticweb.org/ontologies/2023/6/NLnames#",
    "inle_file" : "file://INLE.rdf",
    "ifc_file" : "file://IFC2X3_TC1.rdf",
    "spacy" : "en_core_web_sm"
}