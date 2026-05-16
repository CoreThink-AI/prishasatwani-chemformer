# Brainstorming NRE rules for biochem

Here's an example reasoning process that we could implement and would be useful for any chemistry project... disambiguation of chemical names. LLMs do it poorly. The logical steps are to do a full text search on the name and search for chemicals that have biological uses, based on the number of bioassays recorded in PubChem, number of Vendors that sell it "off the shelf", and any medical uses mentioned in the natural language sections about patents and literature. I'm guessing that Zydus is interested in 5-Fluroimidazole because it is a dopamanine-releasing hormone. It's full canonical name on pubchem is "Thyrotropin releasing hormone 5-fluoroimidazole" which our reasoning engine should classify as a drug and not a starting material or intermediate.

## Fluorinated_Imidazole

### Disambiguation:
- [5-fluoroimidazole CID_56842878](https://pubchem.ncbi.nlm.nih.gov/compound/56842878): 2 vendors, Thyrotropin releasing hormone
- 5-Fluorobenzimidazole CID_235698: 65 vendors, no bioassays
- 2-Fluoroimidazole CID_559542: 38 vendors, few bioassays
- 4-Fluoroimidazole CID_99297: 66 vendors, no bioassays


Q: We are just calling Pubchem API to identify the molecules during target selection, right? How is that different from what you are suggesting?

A: Querying pubchem is an NL search. Chosing the first response is not always the correct answer.
[4:31 PM]The names zydus is querying are ambiguous and spelled differently from what is in pubchem. It takes chemistry reasoning to understand user intent. (edited) 

Q: So how do you think we should implement the disambiguation part?

A: Rerank the search results like a RAG, based on number of Vendors, medical sounding words in the name or patent/literature/manufacturing sections. Or just get an SLM to evaluate. The logic for identifying drug products is just the oposite of the logic for identifying "starting materials". In between we have "intermediate materials." The search result ranking algorithm creates a score using that NL classifier that returns those 3 categories on that spectrum from starting material to drug.
[4:42 PM]The classifier, could just be "ask an SLM" or "logistic regression on Molbart embedding of the smiles for each search result" or just sentiment analysis of the top 10 results on the PubChem search results page or API json.
[4:44 PM]You were brainstorming about reasoning approaches. Rather than thinking about the end-to-end problem of reaction pathway prediction, we've broken down the problem into smaller reasoning steps: 1. reaction prediction 2. molecule classification (drug/starting material, toxicity) 3. disambiguation of common names 4. reaction classification (reasonable yield or not)
[4:46 PM]These are implemented in hard-coded software at the moment (based on simple implicit assumptions by Dhruv or the LLM). I'm just suggesting how you can make these rules explicit and include them in your NRE framework.
[4:48 PM]Mainly just documenting it here for the future, while it's fresh on my mind. We need to be capturing all our hard-coded or manual logic that we are using to get the system working. I'm not suggesting we implement it this week.
[4:49 PM]I'll add these ideas and others to the docs folder on my biochem-db project so you can have them if you want them.
