# https://www.stat4decision.com/fr/traitement-langage-naturel-francais-tal-nlp/
# Ligne de commande: "pip install spacy" + "python -m spacy download fr_core_news_lg" + "pip install bs4" + "pip install lxml"
# Lancer ce programme pour vérifier la bonne installation

import spacy
import json
import sys
import requests
from urllib.request import urlopen
from spacy.matcher import Matcher
from bs4 import BeautifulSoup
from collections import Counter
from string import punctuation

spacy.prefer_gpu()
nlp = spacy.load("fr_core_news_lg")

def token(doc):
    # Tokeniser la phrase
    # Retourner le texte de chaque token
    return [X.text for X in doc]

def PoSTagger(doc):
    print("Pos tagger : ") #PoS tagger
    for token in doc:
        print(token.text, token.lemma_, token.pos_, token.tag_, token.dep_,
              token.shape_, token.is_alpha, token.is_stop)

    print("\nEntité nommée") #NER
    # Analyze syntax
    print("Noun phrases:", [chunk.text for chunk in doc.noun_chunks])
    print("Verbs:", [token.lemma_ for token in doc if token.pos_ == "VERB"])


def NER(nlp):
    #Retourne par exemple PER si l'entité est une personne
    entities = [(token.text, token.label_) for token in nlp.ents]
    print("Document:\n{}\nEntities:\n{}\n\n".format(doc, entities))
    return entities

def get_hotwords(text):
    result = []
    pos_tag = ['PROPN', 'ADJ', 'NOUN'] 
    doc = nlp(text.lower()) 
    for token in doc:
        if(token.text in nlp.Defaults.stop_words or token.text in punctuation):
            continue
        if(token.pos_ in pos_tag):
            result.append(token.text)
    return result

def reponse(question):
    print(question)
    #ANALYSE DU TYPE DE LA QUESTION (via expression régèlière en s'aidant de l'analyse NER):
    #https://spacy.io/usage/rule-based-matching
    matcher = Matcher(nlp.vocab)

    #Recherche d'une personne
    pattern = [{"LOWER": "qui"},{"POS": "AUX"}, {"ENT_TYPE": "PER"}] #QUI + AUXILIAIRE + UN NOM DE PERSONNE (éventuellement prénom + nom de famille) = ON RECHERCHE UNE PERSONNE
    matcher.add("person", None, pattern)
    
    #Recherche d'un lieu
    pattern = [{"LOWER": "où"}]
    matcher.add("Lieu", None, pattern)

    #Recherche d'une date
    pattern = [{"LOWER":{"REGEX": "année|mois|jour|date"}}] #Si la question contient année ou mois ou jour ou date = date
    pattern2 = [{"LOWER":"quand"}, {"POS": "AUX", "OP": "*"}] #Quand + auxiliaire optionnel = date
    matcher.add("Date", None, pattern, pattern2) 

    #Recherche leader d'une ville
    pattern = [{"LOWER":{"REGEX": "maire"}}, {"POS": "ADP", "OP": "*"}, {"POS": "DET", "OP": "*"}, {"ENT_TYPE": "LOC"}]
    matcher.add("mayor", None, pattern)

    #Recherche leader d'un pays
    pattern = [{"LOWER":{"REGEX": "président|president|maire|chef|dirigeant|roi|renne|chancelier|chanceliere|ministre"}}, {"POS": "ADP", "OP": "*"}, {"POS": "DET", "OP": "*"}, {"ENT_TYPE": "LOC"}] #"maire de...", "président de la..."
    matcher.add("Leader_pays", None, pattern)
    
    matches = matcher(question)

    #Traitement selon type de la question
    for match_id, start, end in matches:
        string_id = nlp.vocab.strings[match_id]  # Get string representation
        
        #span = question[start:end]  # The matched span
        #print(match_id, string_id, start, end, span.text)

        #On cherche des informations sur une personne
        if(string_id=="person"):
            return get_abstract(lookup_keyword([(ent.text, ent.label_) for ent in question.ents if ent.label_=="PER"][0][0], string_id)) #On execute la fonction pour faire une requete sur le nom de la personne sur laquelle on veut des informations

        elif(string_id=="mayor"):
            mayor = requete_dbpedia(lookup_keyword([(ent.text, ent.label_) for ent in question.ents if ent.label_=="LOC"][0][0], "Settlement"), "leaderName", "populatedPlace")
            if(mayor == "Aucun résultat correspondant à votre recherche.\n" ):
                return requete_dbpedia(lookup_keyword([(ent.text, ent.label_) for ent in question.ents if ent.label_=="LOC"][0][0], "Settlement"), string_id, "populatedPlace")
            return mayor
        
        elif(string_id=="Leader_pays"):
            return requete_dbpedia(lookup_keyword([(ent.text, ent.label_) for ent in question.ents if ent.label_=="LOC"][0][0], "country"), "leader", "populatedPlace")

def query(q, epr, f='application/json'):
    try:
        params = {'query': q}
        resp = requests.get(epr, params=params, headers={'Accept': f})
        return resp.text
    except Exception as e:
        print(e, file=sys.stdout)
        raise

#La fonction suivante utilise le service lookup pour rechercher à quel label correspont le mot clé entré (par exemple le mot clé "Macron" renverra "Emmanuel Macron")
def lookup_keyword(requete, type):
    xml_content = urlopen("https://lookup.dbpedia.org/api/search/KeywordSearch?QueryClass=" + type + "&QueryString="+requete.replace(" ","%20")).read()  
    soup = BeautifulSoup(xml_content, "xml")
    return soup.Label.string 


def get_abstract(requete):

    json_query = json.loads(query("""prefix dbpedia: <http://dbpedia.org/resource/>
    prefix dbpedia-owl: <http://dbpedia.org/ontology/>
    SELECT DISTINCT ?abstract WHERE { 
        [ rdfs:label ?name
        ; dbpedia-owl:abstract ?abstract
        ] .
        FILTER langMatches(lang(?abstract),"fr")
        VALUES ?name {""" + '"' + requete + '"' + """@en }
        }
        LIMIT 10""","http://dbpedia.org/sparql"))

    #Dans le cas où l'on n'obtient aucun résultat en français on renvoi le résultat anglais
    if(not json_query["results"]["bindings"]):
        json_query = json.loads(query("""prefix dbpedia: <http://dbpedia.org/resource/>
        prefix dbpedia-owl: <http://dbpedia.org/ontology/>
        SELECT DISTINCT ?abstract WHERE { 
        [ rdfs:label ?name
        ; dbpedia-owl:abstract ?abstract
        ] .
        FILTER langMatches(lang(?abstract),"en")
        VALUES ?name {""" + '"' + requete + '"' + """@en }
        }
        LIMIT 10""","http://dbpedia.org/sparql"))

    if(not json_query["results"]["bindings"]):
        return "Aucun résultat correspondant à votre recherche.\n"
    
    return json_query["results"]["bindings"][0]["abstract"]["value"]+'\n'

def requete_dbpedia(requete, type, objet):
    json_query = json.loads(query("""
    prefix dbpedia: <http://dbpedia.org/resource/>
    prefix dbpedia-owl: <http://dbpedia.org/ontology/>
    SELECT DISTINCT ?""" +type + """ WHERE { 
    [ rdfs:label ?"""+ objet + """
    ; dbpedia-owl:"""+type+ '?' + type+"""] .
    VALUES ?"""+objet+ '{'+ '"' + requete +'"' + """@en }
    }
    LIMIT 10""","http://dbpedia.org/sparql"))

    if(not json_query["results"]["bindings"]):
        return "Aucun résultat correspondant à votre recherche.\n"

    json_result=json.loads(query("""SELECT ?label WHERE {<"""+ json_query["results"]["bindings"][0][type]["value"] +"""> rdfs:label ?label. FILTER langMatches(lang(?label),"en")}""", "http://dbpedia.org/sparql"))
    return json_result["results"]["bindings"][0]["label"]["value"]+'\n'
    

    




if __name__ == '__main__':
    #entree = input()
    entree = nlp("Qui est Emmanuel Macron ?")
    print(reponse(entree))

    entree = nlp("Qui est Nicolas Sarkozy ?")
    print(reponse(entree))

    entree = nlp("Qui est Zinedine ?")
    print(reponse(entree))
    
    entree = nlp("Qui est le maire de Paris ?")
    print(reponse(entree))

    entree = nlp("Qui est le maire de New York ?")
    print(reponse(entree))

    entree = nlp("Qui est le maire de Marseille ?")
    print(reponse(entree))

    entree = nlp("Qui est le président des USA ?")
    print(reponse(entree))

    entree = nlp("Qui est le président de la France ?")
    print(reponse(entree))

    """doc = nlp(entree)
    #print(entree)
    PoSTagger(doc)
    print(token(doc))
    sortie = get_hotwords(entree)
    print(sortie)
    NER(doc)
    print(type_question(doc))
    type_question(nlp("Où est Emmanuel Macron ?"))
    type_question(nlp("En quelle année est né Emmanuel Macron ?"))
    print(type_question(nlp("Qui est Nicolas Sarkozy ?")))
    NER(nlp("pont de Brooklyn"))"""