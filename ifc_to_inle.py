#
# parsing of building information in rdf format
# fill instances in an new INLE based ontology
#
# NOTE: ifc step file to rdf/xml format required to be done before
# NOTE: INLE and IFC 2X3 TC1 rdf/xml are required (cf. config.py to set their path)
#
# Warning about rdf source:
# - remove direct imports from rdf file
# - remove any "fake" urls in Ontology IRI and prefixes
# - some URIs/prefixes are httpS
#
# using OwlReady2 (Doc: https://owlready2.readthedocs.io/en/latest/)
#   pip install owlready2
#
# NLP tasks using SpaCy 
#   pip install -U spacy
#   python -m spacy download en_core_web_sm
#
# WorldNet (from nltk) is used for distance metrics
#   pip install --user -U nltk
#

import config

from typing import List, Set, Dict
import time
import csv
import os
import shutil

from owlready2 import *
import spacy
from nltk.metrics.distance import jaro_winkler_similarity as jws_sim

class IfcToINLE:
    def __init__(self, csv_file:str = "ifcTargetList.csv"):
        config.logger.debug("CSV file: %s" % (csv_file))
        start_time = time.time() # execution time

        # init vars
        self.__ifc_targets:List = []
        self.__ifc_objects:Dict = dict()
        self.__nln_ns:Namespace = None # namespace for NLNames
        
        self.nlp = spacy.load(config.main_config["spacy"])    
        self.onto:Ontology = None # in-memory filled INLE onto

        # Load the  ifc objects dictionnary of interest from the CSV file
        if os.path.isfile(csv_file):
            with open('ifcTargetList.csv', mode ='r') as file:
                csvFile = csv.DictReader(file, delimiter=';')
                for row in csvFile:
                   self. __ifc_objects[row['Class']] = row

        config.logger.info("execution time: %s seconds ---" % (time.time() - start_time))

    def __str__(self):
        return ""

    # add variants of a name to the onto
    def __make_nln_variant(self, nln_name, nln_class, nln_basename, nln_base_class, extra_variant):
        #class for variants
        variant_class = getattr(self.__nln_ns, "NLName_Variant")
        nln_variant_name = "nln_Variant_"+nln_basename+"_"

        # origin
        nln_origin_str = nln_name.lower()
        nln_origin_dist = 1.0

        with self.__nln_ns:
            variant_idx = 0
            new_ = variant_class(nln_variant_name+str(variant_idx))
            new_.hasString = nln_origin_str
            new_.hasNLNameType.append(self.onto.search_one(iri = "*nlntype_original"))
            new_.hasscore.append(nln_origin_dist)
            nln_class.hasvariant.append(new_)

        # split
        # CamelCase split to do later maybe? (https://stackoverflow.com/questions/29916065/how-to-do-camelcase-split-in-python)
        nln_split = nln_origin_str.translate(str.maketrans({"-":" ", "_":" ", ":":" ", "/":" "})) # remove unwanted seps
        nln_split = self.nlp(nln_split) # tokenize, pos tagging
        nln_split_str = ' '.join([token.text for token in nln_split]) # human readable
        nln_split_dist = round(jws_sim(nln_origin_str, nln_split_str),2)

        if nln_split_dist != 1:
            with self.__nln_ns:
                variant_idx += 1
                new_ = variant_class(nln_variant_name+str(variant_idx))
                new_.hasString = nln_split_str
                new_.hasNLNameType.append(self.onto.search_one(iri = "*nlntype_split"))
                new_.hasscore.append(nln_split_dist)
                nln_class.hasvariant.append(new_)
        
        # compression
        nln_compression = []
        for token in nln_split:
            if token.pos_ not in ["VBZ", "CC", "DT", "EX", "MD", "PDT", "PRP"]: # dropping useless/noisy tags
                nln_compression.append(token.text)
        nln_compression_str = ' '.join(nln_compression) # human readable
        nln_compression_dist = round(jws_sim(nln_origin_str, nln_compression_str),2)

        if nln_compression_dist != 1 and nln_compression_str != nln_split_str:
            with self.__nln_ns:
                variant_idx += 1
                new_ = variant_class(nln_variant_name+str(variant_idx))
                new_.hasString = nln_compression_str
                new_.hasNLNameType.append(self.onto.search_one(iri = "*nlntype_compression"))
                new_.hasscore.append(nln_compression_dist)
                nln_class.hasvariant.append(new_)

        # lemma
        nln_lemma_str = ' '.join([token.lemma_ for token in nln_split]) # human readable
        nln_lemma_dist = round(jws_sim(nln_origin_str, nln_lemma_str),2)

        if nln_lemma_dist != 1 and nln_lemma_str != nln_split_str:
            with self.__nln_ns:
                variant_idx += 1
                new_ = variant_class(nln_variant_name+str(variant_idx))
                new_.hasString = nln_lemma_str
                new_.hasNLNameType.append(self.onto.search_one(iri = "*nlntype_lemma"))
                new_.hasscore.append(nln_lemma_dist)
                nln_class.hasvariant.append(new_)

        # extra variant for special classes (eg BuildingStorey)
        if extra_variant is None or len(extra_variant) == 0:
            return # EXIT here if no further variants
        
        # synonym
        # get the synonyms from the class
        iname_class = getattr(self.__nln_ns, "NLName_InstanceName")
        class_synonyms = []
        origin_format = None
        for i in nln_base_class.instances():
            if i.is_a == iname_class: # instance name are not class level 
                continue

            synonym = i.hasString.first()
            if synonym is None:
                continue # no string

            if nln_origin_str.find(synonym) != -1:
                origin_format = nln_origin_str.replace(synonym, "%s")
            else:
                class_synonyms.append(synonym)

        if origin_format is not None:
            for synonym in class_synonyms:
                nln_synonym_str = origin_format % synonym # human readable
                nln_synonym_dist = round(jws_sim(nln_origin_str, nln_synonym_str),2)

                with self.__nln_ns:
                    variant_idx += 1
                    new_ = variant_class(nln_variant_name+str(variant_idx))
                    new_.hasString = nln_synonym_str
                    new_.hasNLNameType.append(self.onto.search_one(iri = "*nlntype_synonym"))
                    new_.hasscore.append(nln_synonym_dist)
                    nln_class.hasvariant.append(new_)    

    # enforce ifc base iri
    def update_ifc_iri(self, rdf_file:str, onto:Ontology):
        config.logger.debug("RDF file: %s" % rdf_file)
        # execution time
        start_time = time.time()

        ifc_onto:Ontology = None
        ifc_ns:str = ""

        # get the ifc namespace currently used 
        ifc_objects = onto.search(iri="*IfcApplication")

        for obj in ifc_objects:
            if Thing in obj.is_a:
                ifc_ns = obj.namespace.base_iri
                break

        if ifc_ns != config.main_config["ifc_iri"]:
            # create a temporary ifc ontology
            ifc_onto = get_ontology(ifc_ns)
            # change its base IRI
            ifc_onto.base_iri = config.main_config["ifc_iri"]
            # save the changes in the main onto
            onto.save(rdf_file)

        config.logger.info("execution time: %s seconds ---" % (time.time() - start_time))

    # parsing an ifc rdf file to return a list of objects
    def parse_rdf(self, rdf_src):
        config.logger.debug("Source file: %s" % rdf_src)
        # execution time
        start_time = time.time()

        onto_src:Ontology = None
        ifc_ns:Namespace = None

        # list of kept ifc object to be filled
        self.__ifc_targets.clear()
        
        # load rdf source (from ifctordf)
        onto_src = get_ontology(rdf_src).load()
        config.logger.debug("ignoring class %s" % [prop for prop in onto_src.annotation_properties()])

        # make sure the ifc iri is the one relied upon
        self.update_ifc_iri(rdf_src, onto_src)

        ifc_ns = onto_src.get_namespace(config.main_config["ifc_iri"]) 

        for obj in self.__ifc_objects.values():
            if obj['Keep'] == "0":
                config.logger.info("ignoring class %s" % obj['Class'])
                continue
            
            if not hasattr(ifc_ns, obj['Class']):
                config.logger.warning("no class %s" % obj['Class'])
                continue
            
            ifc_class = getattr(ifc_ns, obj['Class'])

            if not hasattr(ifc_class, "instances"):
                config.logger.warning("no instance of type %s" % obj['Class'])
                continue

            if obj['MapTo']: config.logger.info("class %s is mapped to class %s" % (obj['Class'], obj['MapTo']))
            
            for i in ifc_class.instances():
                target = dict()

                # IfcTypeObject
                if obj['MapTo']:
                    target['IfcTypeObject_Name'] = obj['MapTo']
                else:
                    target['IfcTypeObject_Name'] = obj['Class']

                target['IfcTypeObject_IRI'] = i.is_a.first().iri

                # name_IfcRoot
                target['name_IfcRoot'] = i.name_IfcRoot.first().hasString.first()

                # objectType_IfcObject
                target['objectType_IfcObject'] = None
                if i.objectType_IfcObject:
                    target['objectType_IfcObject'] = i.objectType_IfcObject.first().hasString.first()

                # tag_IfcElement
                target['tag_IfcElement'] = None
                if i.tag_IfcElement:
                    target['tag_IfcElement'] = i.tag_IfcElement.first().hasString.first()

                self.__ifc_targets.append(target)

        config.logger.info("execution time: %s seconds ---" % (time.time() - start_time))

    # fill an inle based ontology from ifc objects
    def fill_inle(self, rdf_tgt):
        config.logger.debug("Target file: %s" % rdf_tgt)
        # execution time
        start_time = time.time()

        # load INLE seed ontology, to fill with selected element from source rdf
        self.onto = get_ontology(config.main_config["inle_file"]).load()
        self.__nln_ns = self.onto.get_namespace(config.main_config["nln_iri"])

        # class for instance names
        iname_class = getattr(self.__nln_ns, "NLName_InstanceName")

        with self.__nln_ns:
            for target in self.__ifc_targets:
                # main object
                class_ = getattr(self.__nln_ns, "NLName_"+target['IfcTypeObject_Name'])
                # clean the name of instance for human readibility
                basename_ = target['name_IfcRoot'].translate(str.maketrans({" ":"", "(":"_", ")":"_", "[":"_", "]":"_"}))
                new_ = class_("nln_InstanceName_"+basename_) 
                new_.is_a.append(iname_class)
                # name from the IFC onto
                new_.hasString = target['name_IfcRoot'] 
                # variant names
                extra_variant = self.__ifc_objects.get(target['IfcTypeObject_Name']).get('ExtraVariant')
                self.__make_nln_variant(target['name_IfcRoot'], new_, basename_, class_, extra_variant)

        # save the INLE version
        self.onto.save(file = rdf_tgt, format = "rdfxml")
        config.logger.info("execution time: %s seconds ---" % (time.time() - start_time))

    def convert_single_file(self, rdf_src:str):
        config.logger.debug("Source file: %s" % rdf_src)
        # execution time
        start_time = time.time()

        # rename src file with _ifc
        if "_ifc.rdf" not in rdf_src: # TODO put _ifc and _inle and .rdf in config
            rdf_old = rdf_src
            rdf_src = rdf_src.replace(".rdf","_ifc.rdf")
            shutil.copyfile(rdf_old, rdf_src)

        rdf_tgt = rdf_src.replace("_ifc.rdf","_inle.rdf")

        self.parse_rdf(rdf_src)
        self.fill_inle(rdf_tgt)

        config.logger.info("execution time: %s seconds ---" % (time.time() - start_time))
    
# for direct use
if __name__ == "__main__":

    # source rdf file with IFC objects
    local_folder = os.getcwd()
    rdf_src = os.path.join(local_folder,"Duplex_A_20110505.rdf")

    converter = IfcToINLE()

    converter.convert_single_file(rdf_src)
