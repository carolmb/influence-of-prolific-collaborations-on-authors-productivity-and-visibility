import glob, json
import numpy as np
import pandas as pd
import dask.dataframe as dd
import matplotlib.pyplot as plt
from scipy.stats import rankdata
from scipy.stats import pearsonr, spearmanr
from matplotlib.colors import LogNorm

from functools import partial
from multiprocessing import Pool
import tqdm


def get_h_index(papers_cits):
    hindex = None
    if len(papers_cits) == 0:
        hindex = (0, 0, 0)
    else:
        hindex_list = []
        papers_cits = sorted(papers_cits, reverse=True)
        htemp = 0
        while htemp != 1 and len(hindex_list) <= 3:
            if papers_cits[-1] - sum(hindex_list) >= len(papers_cits):
                htemp = len(papers_cits) - sum(hindex_list)
            else:
                for i, cits in enumerate(papers_cits):
                    if i+1 == cits - sum(hindex_list): # 100, 20, 30, 4, 4
                        htemp = i+1
                        break
                    elif i+1 > cits - sum(hindex_list):
                        htemp = i
                        break
            hindex_list.append(htemp)
        while len(hindex_list) <= 3:
            hindex_list.append(0)
        hindex = tuple(hindex_list[:3])
    return hindex


def _step_1(data):
    CH = []
    H = []
    C = []
    P = []
    WS = []
    WP = []
    CL = []
    Y = []
    FOS = []
    for _, row in tqdm.tqdm(data.iterrows()):
        c = json.loads(row['citation_count'])
        b = row['birth_year']

        if np.isnan(b):
            print(row['author_id'])
            ValueError('A very specific bad thing happened. OH NO (line 62)')

        h_index = get_h_index(c)
    #     row['h_index'] = h_index
        total_cits = sum(c)
    #     row['total_cits'] = total_cits
        papers = len(c)
    #     row['n_papers'] = papers

        max_w = 0
        max_p = 0
        s = 0
        clist = []
    #     weights = []
        author_colabs = json.loads(row['cits'])
        s = 0

        for colab, colab_infos in author_colabs.items():
            colab_temp = []
            for temp in colab_infos:
                if type(temp) == type([1]):
                    colab_temp += temp
                else:
                    colab_temp.append(temp)
            colab_infos = colab_temp
            w = sum(colab_infos)/total_cits
            if max_w < w:
                max_w = w
                max_p = len(colab_infos)/papers
                clist = colab_infos
                
    #             weights.append(w)
            s += w

        H.append(h_index)
        C.append(total_cits)
        P.append(papers)
        WS.append(max_w)
        WP.append(max_p)
        CL.append(clist) # colab list
        Y.append(b)
        FOS.append(row['fos'])
        CH.append(c) # complete list
    #     row['max_ws'] = max_w
    #     row['max_colabs'] = max_p
    #     row['colab_cit_list'] = clist
    #     return row
    return H, C, P, WS, WP, CL, Y, CH, FOS


def step_1(pairs_authors_dd):
    from dask.diagnostics import ProgressBar
#     with ProgressBar():
#         res = pairs_authors_dd.apply(_step_1, axis=1, meta=[('weights', object), ('fos', int), ('cits', object), 
#                                                             ('birth_year', int),  ('citation_count', object), ('h_index', int), 
#                                                             ('total_cits', int), ('n_papers', int), ('max_ws', float), 
#                                                             ('max_colabs', float),('colab_cit_list', object)])
                                     
#     print(res.head())
    return _step_1(pairs_authors_dd)
#     return res


def step_2(cits, birth, n_papers, max_colabs, suffix=''):
    plt.hist(max_colabs, bins=100)
    plt.title('percentage of colabs with the main colaborator')
    plt.tight_layout()
    plt.savefig('outputs/max_colab_perc%s.pdf' % suffix)
    plt.close()
    
    plt.hist(birth, bins=70)
    plt.yscale('log')
    plt.title('birth year histogram')
    plt.tight_layout()
    plt.savefig('outputs/birth_dist%s.pdf' % suffix)
    plt.close()

    plt.hist(n_papers, bins=100)
    plt.yscale('log')
    plt.title('number of papers histogram')
    plt.tight_layout()
    plt.savefig('outputs/n_papers_dist%s.pdf' % suffix)
    plt.close()
    
    xspace = np.logspace(np.log10(min(cits)), np.log10(max(cits)), 10)
    plt.hist(cits, bins=xspace)
    plt.xscale('log')
    plt.yscale('log')
    plt.title('citations histogram')
    plt.tight_layout()
    plt.savefig('outputs/cits_dist%s.pdf' % suffix)
    plt.close()


def step_3(valid_max_ws, valid_n_papers, valid_cits, valid_birth, suffix=''): 

    ax = plt.axes()
    ax.set_facecolor("black")
    y_space = np.linspace(min(valid_max_ws), max(valid_max_ws), 10)
    x_space = np.logspace(np.log10(min(valid_n_papers)), np.log10(max(valid_n_papers)+1), 10)
    plt.hist2d(valid_n_papers,valid_max_ws, bins=(x_space, y_space), cmap='inferno', norm=LogNorm())
    # plt.hexbin(n_papers,max_incident_out, bins='log', cmap='inferno',xscale="log",marginals=False)
    print(x_space)
    plt.xscale('log')
    plt.xlabel('number of papers')
    plt.ylabel('max(incident, mode=out)')
    plt.title("spearman=%.2f pearson=%.2f" % (spearmanr(valid_n_papers, valid_max_ws)[0], pearsonr(valid_n_papers, valid_max_ws)[0]))
    plt.colorbar()
    plt.savefig('outputs/number_of_papers_max_incident_out%s.pdf' % suffix)
    plt.close()

    idxs = np.searchsorted(x_space, valid_n_papers)
    for idx in set(idxs):
        values_idxs = valid_max_ws[idxs == idx]
        plt.hist(values_idxs, bins=100)
        plt.title('%d < n_papers <= %d \n'% (x_space[idx-1], x_space[idx]) + r'$\mu=%.3f, \sigma=%.3f$' %(np.mean(values_idxs), np.std(values_idxs)))
        plt.xlabel('max(incident, mode=out)')
        plt.tight_layout()
        plt.savefig('outputs/n_papers_max_incident_mode_out_%d_%d%s.pdf' % (x_space[idx-1], x_space[idx], suffix))
        plt.close()
    
    
    # -----------------------------------------------------------------------------

    ax = plt.axes()
    ax.set_facecolor("black")
    # plt.hexbin(age,max_incident_out, bins='log', cmap='inferno',marginals=False)
    plt.hist2d(valid_birth, valid_max_ws, cmap='inferno', norm=LogNorm())
    plt.xlabel('birth year')
    plt.ylabel('max(incident, mode=out)')
    plt.title("spearman=%.2f pearson=%.2f" % (spearmanr(valid_birth, valid_max_ws)[0], pearsonr(valid_birth, valid_max_ws)[0]))
    plt.colorbar()
    plt.tight_layout()
    plt.savefig('outputs/age_max_incident_out%s.pdf' % suffix)
    plt.close()

    x_space = np.linspace(min(valid_birth), max(valid_birth), 10)
    idxs = np.searchsorted(x_space, valid_birth)
    for idx in set(idxs):
        plt.hist(valid_max_ws[idxs == idx], bins=100)
        plt.title('%d < birth year <= %d' % (x_space[idx-1], x_space[idx]))
        plt.xlabel('max(incident, mode=out)')
        plt.savefig('outputs/birth_max_incident_out_%d_%d%s.pdf' %(x_space[idx-1], x_space[idx], suffix))
        plt.close()
    
    # -----------------------------------------------------------------------------
    
    ax = plt.axes()
    ax.set_facecolor("black")
    # plt.hexbin(n_papers,age, bins='log', cmap='inferno',xscale="log",marginals=False)
    plt.hist2d(valid_n_papers, valid_birth, cmap='inferno', norm=LogNorm())
    plt.xlabel('number of papers')
    plt.ylabel('birth year')
    plt.title("spearman=%.2f pearson=%.2f" % (spearmanr(valid_n_papers, valid_birth)[0], pearsonr(valid_n_papers, valid_birth)[0]))
    plt.colorbar()
    plt.tight_layout()
    plt.savefig('outputs/number_of_papers_age%s.pdf' % suffix)
    plt.close()
    
    x_space = np.linspace(min(valid_n_papers), max(valid_n_papers), 10)
    idxs = np.searchsorted(x_space, valid_n_papers)
    for idx in set(idxs):
        plt.hist(valid_birth[idxs == idx], bins=30)
        plt.title('%d < n_papers <= %d' % (x_space[idx-1], x_space[idx]))
        plt.xlabel('birth year')
        plt.tight_layout()
        plt.savefig('outputs/n_paper_birth_%d_%d%s.pdf' % (x_space[idx-1], x_space[idx], suffix))
        plt.close()
    
    # -----------------------------------------------------------------------------
    ax = plt.axes()
    ax.set_facecolor("black")
    # plt.hexbin(n_papers,cits, bins='log', cmap='inferno',xscale="log", yscale='log',marginals=False)
    x_space = np.linspace(min(valid_n_papers), max(valid_n_papers), 10)
    y_space = np.logspace(np.log10(min(valid_cits)), np.log10(max(valid_cits)), 10)
    plt.hist2d(valid_n_papers, valid_cits, cmap='inferno', norm=LogNorm(), bins=(x_space, y_space))
    plt.yscale('log')
    plt.xlabel('number of papers')
    plt.ylabel('citations')
    plt.title("spearman=%.2f pearson=%.2f" % (spearmanr(valid_n_papers, valid_cits)[0], pearsonr(valid_n_papers, valid_cits)[0]))
    plt.colorbar()
    plt.tight_layout()
    plt.savefig('outputs/number_of_papers_citations%s.pdf' % suffix)
    plt.close()

    idxs = np.searchsorted(x_space, valid_n_papers)
    for idx in set(idxs):
        values_idxs = valid_cits[idxs == idx]
        plt.hist(values_idxs, bins=y_space)
        plt.title('%d < n_papers <= %d \n'% (x_space[idx-1], x_space[idx]) + r'$\mu=%.3f, \sigma=%.3f$' %(np.mean(values_idxs), np.std(values_idxs)))
        plt.xlabel('citations')
        plt.xscale('log')
        plt.tight_layout()
        plt.savefig('outputs/n_papers_citations_%d_%d%s.pdf' % (x_space[idx-1], x_space[idx], suffix))
        plt.close()
        
    #--------------------------------------------------------------------------------
    ax = plt.axes()
    ax.set_facecolor("black")
    # plt.hexbin(cits, age, bins='log', cmap='inferno',xscale="log",marginals=False)
    x_space = np.logspace(np.log10(min(valid_cits)), np.log10(max(valid_cits)), 10)
    y_space = np.linspace(min(valid_birth), max(valid_birth), 10)
    plt.hist2d(valid_cits, valid_birth, cmap='inferno', norm=LogNorm(), bins=(x_space, y_space))
    plt.xscale('log')
    plt.xlabel('citations')
    plt.ylabel('birth year')
    plt.title("spearman=%.2f pearson=%.2f" % (spearmanr(valid_cits, valid_birth)[0], pearsonr(valid_cits, valid_birth)[0]))
    plt.colorbar()
    plt.tight_layout()
    plt.savefig('outputs/citations_age%s.pdf' % suffix)
    plt.close()

    idxs = np.searchsorted(x_space, valid_cits)
    for idx in set(idxs):
        if idx == len(x_space):
            continue
        valid_idxs = valid_birth[idxs == idx]
        plt.hist(valid_idxs, bins=30)
        plt.title('%d < citations <= %d \n' % (x_space[idx-1], x_space[idx]) + r'$\mu=%.3f, \sigma=%.3f$' % (np.mean(valid_idxs), np.std(valid_idxs)))
        plt.xlabel('birth year')
    #     plt.xscale('log')
        plt.tight_layout()
        plt.savefig('outputs/citations_birth_%d_%d%s.pdf' % (x_space[idx-1], x_space[idx], suffix))
        plt.close()
        

def step_4(valid_h_index, valid_colabs_cit_list, valid_citation_list, suffix=''):
    
    hindex_after = []
    for ccits, acits in zip(valid_colabs_cit_list, valid_citation_list):
        diff_cits = acits.copy()
        for ctemp in ccits:
            diff_cits.remove(ctemp)
        hafter = get_h_index(diff_cits)
        hindex_after.append(hafter)
    

    hindex_before_l1 = np.asarray([row[0] for row in valid_h_index])
    print(hindex_before_l1[:10])
    hindex_after_l1 = np.asarray(hindex_after)[:,0]
    print(hindex_after_l1[:10])

    for h in range(10, 100, 5):
        idxs_h10 = hindex_before_l1 == h
        plt.hist(hindex_after_l1[idxs_h10])
        plt.yscale('log')
        plt.title('h-index %d' % h)
        plt.savefig('outputs/h_index_level1_%d%s.pdf' % (h, suffix))
        plt.close()
        
    ax = plt.axes()
    ax.set_facecolor("black")
    ax.set_aspect('equal')
    plt.hist2d(hindex_before_l1[hindex_before_l1 <= 25], hindex_after_l1[hindex_before_l1 <= 25], 
           norm=LogNorm(), cmap='inferno', bins=(25, 25))
    # plt.yscale('log')
    plt.xlabel('h-index before')
    plt.ylabel('h-index after')
    # plt.title("spearman=%.2f pearson=%.2f" % (spearmanr(valid_n_papers, valid_cits)[0], pearsonr(valid_n_papers, valid_cits)[0]))
    plt.colorbar()
    plt.tight_layout()
    plt.savefig('outputs/hindex_level_1_before_after%s.pdf' % suffix)
    plt.close()
    
    return hindex_after 


def rank(values, i, new_val):
    old = values[i]
    new_pair = np.array([(new_val[0], new_val[1], new_val[2], old[3])], dtype=[('my_val1', int), ('my_val2', int), ('my_val3', int), ('my_val4', int)])
    new_rank = np.searchsorted(values, new_pair[0], side='right')
    return new_rank


def get_rank_after(hindexbefore, i, ccits, acits):
    diff_cits = acits.copy()
    for ctemp in ccits:
        diff_cits.remove(ctemp)
    hafter = get_h_index(diff_cits)
    rafter = rank(hindexbefore, i, (-hafter[0], -hafter[1], -hafter[2]))
    return rafter


def step_5(valid_h_index, hindex_after, valid_colabs_cit_list, valid_citation_list, suffix=''):
    neg_hindex = np.array([(-row[0], -row[1], -row[2], i) for i,row in enumerate(valid_h_index)], dtype=[('my_val1', int), ('my_val2', int), ('my_val3', int), ('my_val4', int)])
    neg_hindex_sorted = np.sort(neg_hindex)
    rankbefore = rankdata(neg_hindex, method='ordinal')
    
#     pool = Pool(16)
#     results = pool.starmap(partial(get_rank_after,neg_hindex), 
#                        zip(np.arange(len(neg_hindex)), valid_colabs_cit_list, valid_citation_list))
    results = []
    for a,b,c in tqdm.tqdm(zip(np.arange(len(neg_hindex)), valid_colabs_cit_list, valid_citation_list), total=len(neg_hindex)):
        results.append(get_rank_after(neg_hindex_sorted, a,b,c)) 
    
    plt.figure(figsize=(7,7))
    ax = plt.axes()
    ax.set_facecolor("black")
    ax.set_aspect('equal')
    # x_space = np.logspace(np.log10(min(all_cits)), np.log10(all_cits), 50)
    # y_space = np.linspace(min(), max(), 50)

    plt.hist2d(rankbefore, results, bins=50, cmap='inferno', norm=LogNorm())
    plt.title('pearson = %.2f' % pearsonr(rankbefore, results)[0])
    plt.xlabel('author\'s rank by h-index')
    plt.ylabel('author\'s rank by h-index\n excluding their main collaborator')
    plt.colorbar()
    ax = plt.gca()
    ax.invert_yaxis()
    # ax.invert_xaxis()
    plt.tight_layout()
    plt.savefig('outputs/h_index_rank%s.pdf' % suffix)
    plt.close()
    

def rank_cits(values, i, new_val):
    old = values[i]
    new_pair = np.array([(new_val, old[1])], dtype=[('my_val1', int), ('my_val2', int)])
    new_rank = np.searchsorted(values, new_pair[0], side='right')
    return new_rank

    
def get_rank_after_cits(hindexbefore, i, ccits, acits):
    diff_cits = acits.copy()
    for ctemp in ccits:
        diff_cits.remove(ctemp)
    hafter = - sum(diff_cits)
    rafter = rank_cits(hindexbefore, i, hafter)
    return rafter


def step_6(cits, colabs_cits, cits_list, suffix=''):
    cits = cits[:1000]
    neg_hindex = np.array([(-row, i) for i,row in enumerate(cits)], dtype=[('my_val1', int), ('my_val2', int)])
    rankbefore = rankdata(neg_hindex, method='ordinal', axis=0)
    rankbefore = list(zip(rankbefore, np.arange(len(rankbefore))))
    
    pool = Pool(16)
    results = pool.starmap(partial(get_rank_after_cits, neg_hindex), 
                       zip(np.arange(len(neg_hindex)), colabs_cits, cits_list))
    
    print(results)
    return
    plt.figure(figsize=(7,7))
    ax = plt.axes()
    ax.set_facecolor("black")
    ax.set_aspect('equal')
    # x_space = np.logspace(np.log10(min(all_cits)), np.log10(all_cits), 50)
    # y_space = np.linspace(min(), max(), 50)

    plt.hist2d(rankbefore, results, bins=50, cmap='inferno', norm=LogNorm())
    plt.xlabel('author\'s rank by citation')
    plt.ylabel('author\'s rank by citation\n excluding their main collaborator')
    plt.colorbar()
    ax = plt.gca()
    ax.invert_yaxis()
    # ax.invert_xaxis()
    plt.tight_layout()
    plt.savefig('outputs/citation_rank%s.pdf' % suffix)
    plt.close()
    

def plot_quantile(authors, group, title, quantile_values, neg_hindex, valid_colabs_cit_list, valid_citation_list, suffix=''):
    X = []
    Y = []
    authors = np.asarray(authors)
    
    rankbefore = rankdata(neg_hindex, method='ordinal', axis=0)
    rankbefore = list(zip(rankbefore, np.arange(len(rankbefore))))
    
    pool = Pool(16)
    results = pool.starmap(partial(get_rank_after,neg_hindex), 
                           zip(np.arange(len(neg_hindex)), valid_colabs_cit_list[authors], valid_citation_list[authors]))
    
    ax = plt.axes()
    ax.set_facecolor("black")
    ax.set_aspect('equal')
    # x_space = np.logspace(np.log10(min(all_cits)), np.log10(all_cits), 50)
    # y_space = np.linspace(min(), max(), 50)
    X = rankbefore[authors]
    Y = results
    plt.hist2d(X, Y, bins=50, cmap='inferno', norm=LogNorm())
    ax = plt.axes()
    ax.invert_yaxis()
    
    plt.xlabel('author\'s rank by h index')
    plt.ylabel('author\'s rank by h index\n excluding their main collaborator')
    plt.title('quantile %d < %s <= %d' % (quantile_values[group-1], title, quantile_values[group]))
    plt.colorbar()
    plt.tight_layout()
    plt.savefig('outputs/rank_q%d_%s_hindex%s.pdf' % (group, title, suffix))
    plt.clf()

    
def step_7(h_index, valid_cits, valid_n_papers, valid_birth, colabs_cit_list, citation_list, suffix=''):
    
    neg_hindex = np.array([(-row[0], -row[1], -row[2]) for row in h_index], dtype=[('my_val1', int), ('my_val2', int), ('my_val3', int)])
    
    quantile_cits = np.quantile(valid_cits, [0, 0.25, 0.5, 0.75, 1])
    quantile_cits[-1] += 1
    print(quantile_cits)

    quantile_n_papers = np.quantile(valid_n_papers, [0, 0.25, 0.5, 0.75, 1])
    quantile_n_papers[-1] += 1
    print(quantile_n_papers)

    quantile_birth = np.quantile(valid_birth, [0, 0.25, 0.5, 0.75, 1])
    quantile_birth[-1] += 1
    print(quantile_birth)
    
    from collections import defaultdict
    authors_by_cits = defaultdict(lambda: [])
    for i in range(len(valid_cits)):
        idx = np.searchsorted(quantile_cits, valid_cits[i], side='right')
        authors_by_cits[idx].append(i)

    authors_by_n_papers = defaultdict(lambda: [])
    for i in range(len(valid_n_papers)):
        idx = np.searchsorted(quantile_n_papers, valid_n_papers[i], side='right')
        authors_by_n_papers[idx].append(i)

    authors_by_birth = defaultdict(lambda: [])
    for i in range(len(valid_birth)):
        idx = np.searchsorted(quantile_birth, valid_birth[i], side='right')
        authors_by_birth[idx].append(i)

    for group, authors in authors_by_cits.items():    
        plot_quantile(authors, group, 'cits', quantile_cits, neg_hindex, colabs_cit_list, citation_list, suffix)

    for group, authors in authors_by_n_papers.items():    
        plot_quantile(authors, group, 'n_papers', quantile_n_papers, neg_hindex, colabs_cit_list, citation_list, suffix)

    for group, authors in authors_by_birth.items():    
        plot_quantile(authors, group, 'year', quantile_birth, neg_hindex, colabs_cit_list, citation_list, suffix)
        
        
if __name__ == '__main__':
   
    pairs_authors_dd = dd.read_csv('data/PairAuthors2csv_split/pair_processed_join*', sep='\t', header=None, names=['author_id', 'cits'])
    
    h_index, cits, n_papers, birth, max_ws, max_colabs, citation_list, colabs_cit_list, _ = step_1(pairs_authors_dd)
    
#     step_2(cits, birth, n_papers, max_colabs) # basic distributions
    
#     step_3(max_ws, n_papers, cits, birth)
    
    hindex_after = step_4(h_index, colabs_cit_list, citation_list, 'newrankfunk')
    
    step_5(h_index, hindex_after, colabs_cit_list, citation_list, 'newrankfunk')

#     step_6(cits, colabs_cit_list, citation_list)

#     step_7(h_index, cits, n_papers, birth, colabs_cit_list, citation_list)