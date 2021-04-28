import json
import gzip, glob
import pandas as pd
import dask.dataframe as dd
import os, csv
import numpy as np
import multiprocessing
from collections import defaultdict
from functools import partial
import codecs


def step_1():
    import sys
    print(sys.stdout.encoding)
    header = '/mnt/e/MAG/mag-2021-01-05/'
    papers = 'mag/Papers.txt'
    
    for chunk in pd.read_csv(header+papers, header=None, sep='\t', encoding='utf-8',
                             quoting=csv.QUOTE_NONE,
                            chunksize=100000):# , #error_bad_lines=False):
        valid_chunk = chunk[[0, 2, 7, 19]]
        
        valid_chunk.to_csv('data_temp/papers_filtered_1.txt', sep='\t', mode='a',
                           header=False, index=False)


def step_2():
    # sort --parallel=20 -Tdata_temp -t$'\t' -nk1 data_temp/papers_filtered_1.txt > data/papers_filtered_1_byPaperID.txt
    pass


def step_3():
    header = '/mnt/e/MAG/mag-2021-01-05/'
    paper_refs = 'mag/PaperReferences.txt'
    paper_refs = dd.read_csv(header+paper_refs, header=None, sep='\t', names = ['paper_id', 'paper_reference_id'])
#                          dtype={'paper_id': 'Int64', 'paper_reference_id': 'Int64'})

    papers = dd.read_csv('data/papers_filtered_1_byPaperID.txt', header=None, sep='\t',
                         names=['paper_id', 'doi', 'year', 'citation_count'], 
                         dtype={'citation_count': 'object',
                           'year': 'object'})

    paper_refs = paper_refs.set_index('paper_id', sorted=True)
    papers = papers.set_index('paper_id', sorted=True)
    join_result = paper_refs.merge(papers, left_index=True, right_index=True)
    join_result.to_csv('data_temp/paper_refs_year.txt', sep='\t', single_file=True, header=False)


def step_4():
    # sort --parallel=20 -Tdata_temp -t$'\t' -nk2 data_temp/paper_refs_year.txt > data_temp/paper_refs_year_byReferenceID.txt
    pass


def step_5():
    # split -l 1000000 -a 5 -d /mnt/e/MAG/mag-2021-01-05/mag/PaperAuthorAffiliations.txt data_temp/AuthorAffili_split/author_affil_
    # split -l 1000000 -a 5 -d data_temp/paper_refs_year_byReferenceID.txt data_temp/PaperRefsYear_split/paper_ref_year_
    pass
# IF author_affil is .gz:

#     header = '/mnt/e/MAG/mag-2021-01-05/'
#     authors_affil = 'mag/PaperAuthorAffiliations.txt.gz'
#     i = 0
#     j = 0
#     with gzip.open(header+authors_affil, 'rb') as infile:
#         to_write = ''
#         for line in infile:
#             to_write += line.decode('utf-8')
#             i += 1

#             if i%1000000 == 0:
#                 f = open('data_temp/AuthorAffili_split/author_affili_%d.txt' % j, 'w')
#                 f.write(to_write)
#                 f.close()
#                 to_write = ''
#                 j += 1

#         if len(to_write) > 0:
#             f = open('data_temp/AuthorAffili_split/author_affili_%d.txt' % j, 'w')
#             f.write(to_write)
#             f.close()


def json_years(years):
    temp = defaultdict(lambda:0)
    for year in years:
        temp[str(year)[:4]] += 1
    temp = json.dumps(temp)
    return temp


def concat_json(json_1, values_2):
    json_dict = json.loads(json_1)
    for value in values_2:
        key = str(value)[:4]
        if key in json_dict:
            json_dict[key] += 1
        else:
            json_dict[key] = 1
    return json.dumps(json_dict)


def papers_citations(inputfile):
    i = int(inputfile.split('_')[-1])
    chunk = pd.read_csv('data_temp/PaperRefsYear_split/'+inputfile, header=None,
                sep='\t', names=['paper_id', 'reference_id', 'doi', 'year', 'citation'])
    
    output = open("data_temp/PaperCits_split/paper_cit_%05d" % i, 'w')
    
    current_reference = -1
    years = []
    t_citation = 0

    output_text = ''
    if current_reference == -1:
        current_reference = chunk.iloc[0,1]
    for idx,row in chunk.iterrows():
        if current_reference == row['reference_id']:
            years.append(str(row['year']))
            t_citation += 1
        else:
            output.write("%d\t%d\t%s\n" % (current_reference, t_citation, json_years(years)))
            current_reference = row['reference_id']
            years = [str(row['year'])]
            t_citation = 1
    
    output.write("%d\t%d\t%s" % (current_reference, t_citation, json_years(years)))
    output.close()
    

def step_6():  
    pool = multiprocessing.Pool(16)
    inputs = os.listdir('data_temp/PaperRefsYear_split/')

    pool.map(papers_citations, inputs)
    pool.close()
    

def step_7():
    inputs = sorted(glob.glob('data_temp/PaperCits_split/*'))

    panda_concat_final = pd.read_csv(inputs[0], header=None, 
                            sep='\t', names=['paper_id', 'cits', 'years'])
   
    for inputs_idx in inputs[1:]:
        panda_processed_i1 = pd.read_csv(inputs_idx, header=None, 
                            sep='\t', names=['paper_id', 'cits', 'years'])
        
        last_id = panda_concat_final.iloc[-1, 0]
        first_id = panda_processed_i1.iloc[0, 0]
        if last_id == first_id:
            # união
            panda_processed_i1.iloc[0, 1] += panda_concat_final.iloc[-1, 1]
            panda_processed_i1.iloc[0, 2] = concat_json(panda_processed_i1.iloc[0, 2], panda_concat_final.iloc[-1, 2])
            panda_concat_final = panda_concat_final[:-1]
        
        panda_concat_final = panda_concat_final.append(panda_processed_i1, ignore_index=True)

    panda_concat_final.to_csv('data/paper_cits.csv', header=None, index=None, sep='\t')


def join_authors_of_paper(input_name):
    print(input_name)
    chunk = pd.read_csv(input_name, header=None, index_col=False, error_bad_lines=False,
                    encoding='utf-8', quoting=csv.QUOTE_NONE, 
                    sep='\t', names=['paper_id', 'author_id', '11', '22', '33'])

    authors = []

    output_text = ''
    current_reference = chunk.iloc[0,0]
    i = int(input_name.split('_')[-1])
    output = open("data_temp/Colabs_split/paper_authors_%05d" % i, 'w')
    for idx,row in chunk.iterrows():
        if current_reference == row['paper_id']:
            authors.append(str(row['author_id']))
        else:
            output.write("%d\t%s\n" % (current_reference, ','.join(authors)))
            current_reference = row['paper_id']
            authors = [str(row['author_id'])]

    if len(authors) > 0:
        output.write("%d\t%s" % (current_reference, ','.join(authors)))

    output.close()

def step_8():
    pool = multiprocessing.Pool(16)

    inputs = glob.glob('data_temp/AuthorAffili_split/*')

#     input_erros = ['data_temp/AuthorAffili_split/author_affil_00066',
#     'data_temp/AuthorAffili_split/author_affil_00110',
#     'data_temp/AuthorAffili_split/author_affil_00090',
#     'data_temp/AuthorAffili_split/author_affil_00147',
#     'data_temp/AuthorAffili_split/author_affil_00137',
#     'data_temp/AuthorAffili_split/author_affil_00075',
#     'data_temp/AuthorAffili_split/author_affil_00264',
#     'data_temp/AuthorAffili_split/author_affil_00302',
#     'data_temp/AuthorAffili_split/author_affil_00293',
#     'data_temp/AuthorAffili_split/author_affil_00251',
#     'data_temp/AuthorAffili_split/author_affil_00378',
#     'data_temp/AuthorAffili_split/author_affil_00444']
    
    pool.map(join_authors_of_paper,inputs)
    pool.close()
    

def step_9():
    # TODO VERIFICAR SE ESTÁ SORTED SEM USAR SORTED
    inputs = glob.glob('data_temp/Colabs_split/*')
    inputs = sorted(inputs)
    
    panda_concat_final = pd.read_csv(inputs[0], header=None, index_col=False,
                            sep='\t', names=['paper_id', 'authors'])
    
    for inputs_idx in inputs[1:]:
        
        last_id = panda_concat_final.iloc[-1, 0]
        last_refs = panda_concat_final[panda_concat_final['paper_id'] == last_id]['authors']
        n_authors = len(last_refs)


        panda_processed_i1 = pd.read_csv(inputs_idx, header=None, index_col=False,
                            sep='\t', names=['paper_id', 'authors'])
        first_id = panda_processed_i1.iloc[0, 0]

        if last_id == first_id:
            # união
            new_authors = panda_processed_i1.iloc[0, 1] + ',' + ','.join(last_refs)
            panda_processed_i1.iloc[0, 1] = new_authors
            panda_concat_final = panda_concat_final[:-1]
            # contatena
        
        panda_concat_final = panda_concat_final.append(panda_processed_i1, ignore_index=True)

    panda_concat_final.to_csv('data/paper_authors.csv', header=None, index=None, sep='\t')
    

def step_10():
    paper_cits = dd.read_csv('data/paper_cits.csv', header=None, sep='\t', 
                             names = ['paper_id', 'cits', 'years'],
                             dtype={'years': 'string'})
    paper_authors = dd.read_csv('data/paper_authors.csv', header=None, sep='\t',
                         names=['paper_id', 'authors'])
    paper_infos = dd.read_csv('data/papers_filtered_1_byPaperID.txt', header=None, sep='\t',
                        names=['paper_id', 'doi', 'year', 'citation_count'],
                        dtype={'citation_count': 'object', 'year': 'object'})[['paper_id', 'doi', 'year']]
    
    paper_cits = paper_cits.set_index('paper_id', sorted=True)
    paper_authors = paper_authors.set_index('paper_id', sorted=True)
    paper_infos = paper_infos.set_index('paper_id', sorted=True)
    join_result1 = paper_infos.merge(paper_authors, how='left', left_index=True, right_index=True)
    join_result2 = join_result1.merge(paper_cits, how='left', left_index=True, right_index=True)

    join_result2.to_csv('data/paper_complete_infos.csv', sep='\t', single_file=True, header=False)
    
    
if '__main__' == __name__:
#     step_1() # filter erros in papers.txt file to future open on dask
#     step_2()
#     step_3()
#     step_4()
    # step_5()
    print('step 6')
    step_6() # citações dos artigos
    print('step 7')
    step_7() # união dos arquivos de citações dos artigos
    print('step 8')
    step_8() # autores dos artigos
    print('step 9')
    step_9() # união das colaborações dos autores
    print('step 10')
    step_10()


# 249 990 849 authors
# 249 265 454 papers