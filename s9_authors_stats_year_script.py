import glob, json
import numpy as np
import pandas as pd
import s4_authors_stats as s4
import dask.dataframe as dd
import matplotlib.pyplot as plt
from scipy.stats import rankdata
from scipy.stats import pearsonr, spearmanr
from matplotlib.colors import LogNorm


import tqdm
from functools import partial
from multiprocessing import Pool

def fos_sort(max_ws, fos):
    values = []
    fs = []
    count = []
    for field in unique:
        group = max_ws[fos == field]
        if len(group) < 500:
            continue
        median = np.percentile(group, 50)
        fs.append(field)
        values.append(median)
        count.append(len(group))
    values = np.asarray(values)
    fs = np.asarray(fs)
    count = np.asarray(count)
    idxs = np.argsort(values)
    values = values[idxs]
    fs = fs[idxs]
    count = count[idxs]
    
    return fs, count


tempsuffix = 2020
WS = np.asarray(json.load(open('results/ws_full_%d.json' % tempsuffix)))
FOS = np.asarray(json.load(open('results/fos_full_%d.json' % tempsuffix)))
unique = np.unique(FOS)
fos_sorted, _ = fos_sort(WS, FOS)


header = '/mnt/e/MAG/mag-2021-01-05/advanced/'
fields_infos = 'FieldsOfStudy.txt'
fos_infos = pd.read_csv(header+fields_infos, header=None, sep='\t')[[0, 1, 2]]
fos_infos.columns = ['field_id', 'rank', 'normalized_name']


from s4_authors_stats import get_h_index

def _hindex_before_after_temporal(ax, field_name, valid_colabs_cit_list, valid_citation_list, valid_h_index):
    
    hindex_after = []
    
    for ccits, acits in zip(valid_colabs_cit_list, valid_citation_list):
        diff_cits = acits.copy() # json.loads(acits)
        for ctemp in ccits: # json.loads(ccits):
            diff_cits.remove(ctemp)
            
        hafter = get_h_index(diff_cits)
        hindex_after.append(hafter)
    
    hindex_before_l1 = np.asarray([row[0] for row in valid_h_index])
    hindex_after_l1 = np.asarray(hindex_after)[:,0]
    
    ax.set_facecolor("black")
    perc = np.percentile(hindex_before_l1, 99)
    im = ax.hist2d(hindex_before_l1[hindex_before_l1 <= perc], hindex_after_l1[hindex_before_l1 <= perc], 
           norm=LogNorm(), cmap='inferno', bins=(25, 25))
    ax.set_title(field_name)
    
    return im, hindex_after 


def _cits_before_after_temporal(ax, field_name, valid_colabs_cit_list, valid_citation_list, valid_h_index):
    cits_before = []
    cits_after = []
    
    for ccits, acits in zip(valid_colabs_cit_list, valid_citation_list):
        before = sum(acits)
        after = before - sum(ccits)
        
        cits_before.append(before)    
        cits_after.append(after)
    
    cits_before = np.asarray(cits_before)
    cits_after = np.asarray(cits_after)
    
    ax.set_facecolor("black")
    perc = np.percentile(cits_before, 99)
    im = ax.hist2d(cits_before[cits_before <= perc], cits_after[cits_before <= perc], 
           norm=LogNorm(), cmap='inferno', bins=(25, 25))
    ax.set_title(field_name)
    
    return im, cits_after 
    
    
def _papers_before_after_temporal(ax, field_name, valid_colabs_cit_list, valid_citation_list, valid_h_index):
    p_before = []
    p_after = []
    
    for ccits, acits in zip(valid_colabs_cit_list, valid_citation_list):
        before = len(acits)
        after = before - len(ccits)
        
        p_before.append(before)    
        p_after.append(after)
    
    p_before = np.asarray(p_before)
    p_after = np.asarray(p_after)
    
    ax.set_facecolor("black")
    perc = np.percentile(p_before, 99)
    im = ax.hist2d(p_before[p_before <= perc], p_after[p_before <= perc], 
           norm=LogNorm(), cmap='inferno', bins=(25, 25))
    ax.set_title(field_name)
    
    return im, p_after 
    

def hindex_before_after_temporal(get_metric, metric):
    hafter_map = {fos:dict() for fos in fos_sorted}
    for field in fos_sorted:
        fig,axes = plt.subplots(figsize=(21, 3), nrows=1, ncols=7)

        for i, tempsuffix in enumerate(range(1960, 2021, 10)):
            
            FOS = np.asarray(json.load(open('results/fos_full_%d.json' % tempsuffix)))
            X = np.asarray(json.load(open('results/citlist_full_%d.json' % tempsuffix)))
            Y = np.asarray(json.load(open('results/ch_full_%d.json' % tempsuffix)))
            H = np.asarray(json.load(open('results/hindex_full_%d.json' % tempsuffix)))
            idxs = FOS == field
            tempX = X[idxs]
            tempY = Y[idxs]
            tempH = H[idxs]
            im, hafter = get_metric(axes[i], '%d' % tempsuffix, tempX, tempY, tempH)
            hafter_map[field][tempsuffix] = hafter
    
            fig.colorbar(im[3], ax=axes[i])
            axes[i].set_xlabel('h-index before')
            if i == 0:
                axes[i].set_ylabel('h-index after')

        field_name = fos_infos[fos_infos['field_id'] == field].iloc[0, -1]
        fig.suptitle(field_name)
        fig.tight_layout()
        fig.savefig('outputs/fos_hist2d_before_after_%s_%s_temporal.pdf' % (field_name, metric))    
    
    return hafter_map
        
    
def rank(values, i, new_val):
    new_pair = np.array([(new_val[0], new_val[1], new_val[2], i[-1])], dtype=[('my_val1', int), ('my_val2', int), ('my_val3', int), ('my_val4', int)])
    new_rank = np.searchsorted(values, new_pair[0], side='right')
    return new_rank


def get_rank_after(hindexbefore, i, ccits, acits):
    diff_cits = acits.copy() #json.loads(acits)
    for ctemp in ccits: #json.loads(ccits):
        diff_cits.remove(ctemp)
    hafter = get_h_index(diff_cits)
#     print(hafter, i, acits)
    rafter = rank(hindexbefore, i, (-hafter[0], -hafter[1], -hafter[2]))
    return rafter


def rank_cits(values, i, new_val):
    new_pair = np.array([(new_val[0], i[-1])], dtype=[('my_val1', int), ('my_val2', int)])
    new_rank = np.searchsorted(values, new_pair[0], side='right')
    return new_rank


def get_rank_author(hindexbefore, i, citsafter):
    rafter = rank_cits(hindexbefore, i, (-citsafter,))
    return rafter


def _plot_rank_temporal(ax, hindex_after, field_name, valid_h_index, valid_citation_list, valid_colabs_cit_list):
    neg_hindex = np.array([(-row[0], -row[1], -row[2], i) for i,row in enumerate(valid_h_index)], 
                          dtype=[('my_val1', int), ('my_val2', int), ('my_val3', int), ('my_val4', int)])
    
    neg_hindex_sorted = np.sort(neg_hindex)
    rankbefore = rankdata(neg_hindex, method='ordinal')

    temp = 0
    results = []
    for a,b,c in tqdm.tqdm(zip(neg_hindex, valid_colabs_cit_list, valid_citation_list), total=len(neg_hindex)):
        results.append(get_rank_after(neg_hindex_sorted, a,b,c)) 
    
    ax.set_facecolor("black")
    
    im = ax.hist2d(rankbefore, results, bins=50, cmap='inferno', norm=LogNorm())
    ax.set_title('%s \npearson = %.2f' % (field_name, pearsonr(rankbefore, results)[0]))
    ax.invert_yaxis()
    return im


def _plot_rank_cits(ax, metric_after, field_name, valid_h_index, valid_citation_list, valid_colabs_cit_list):
    valid_citation_list2 = [sum(temp) for temp in valid_citation_list]
    
    neg_cits = np.array([(-row, i) for i,row in enumerate(valid_citation_list2)], 
                          dtype=[('my_val1', int), ('my_val2', int)])
    neg_cits_sorted = np.sort(neg_cits)
    rankbefore = rankdata(neg_cits, method='ordinal')

    results = []
    for c, cafter in tqdm.tqdm(zip(neg_cits, metric_after), total=len(neg_cits)):
        results.append(get_rank_author(neg_cits_sorted, c, cafter)) 
    
    ax.set_facecolor("black")
    
    im = ax.hist2d(rankbefore, results, bins=50, cmap='inferno', norm=LogNorm())
    ax.set_title('%s \npearson = %.2f' % (field_name, pearsonr(rankbefore, results)[0]))
    ax.invert_yaxis()
    return im


def _plot_rank_papers(ax, metric_after, field_name, valid_h_index, valid_citation_list, valid_colabs_cit_list):
    valid_papers_list = [len(temp) for temp in valid_citation_list]
    
    neg_cits = np.array([(-row, i) for i,row in enumerate(valid_papers_list)], 
                          dtype=[('my_val1', int), ('my_val2', int)])
    neg_cits_sorted = np.sort(neg_cits)
    rankbefore = rankdata(neg_cits, method='ordinal')

    results = []
    for c, cafter in tqdm.tqdm(zip(neg_cits, metric_after), total=len(neg_cits)):
        results.append(get_rank_author(neg_cits_sorted, c, cafter)) 
    
    ax.set_facecolor("black")
    
    im = ax.hist2d(rankbefore, results, bins=50, cmap='inferno', norm=LogNorm())
    ax.set_title('%s \npearson = %.2f' % (field_name, pearsonr(rankbefore, results)[0]))
    ax.invert_yaxis()
    return im


def plot_rank_temporal(hafter_map, _plot_rank, xlabel, ylabel, outname):

    for field in fos_sorted:
        fig,axes = plt.subplots(figsize=(21, 3), nrows=1, ncols=7)
        for i, tempsuffix in enumerate(range(1960, 2021, 10)):
    
            FOS = np.asarray(json.load(open('results/fos_full_%d.json' % tempsuffix)))
            
            H = np.asarray(json.load(open('results/hindex_full_%d.json' % tempsuffix)))
            X = np.asarray(json.load(open('results/ch_full_%d.json' % tempsuffix)))
            Y = np.asarray(json.load(open('results/citlist_full_%d.json' % tempsuffix)))
            
            idxs = FOS == field
            tempX = X[idxs]
            tempY = Y[idxs]
            tempH = H[idxs]
            
    
            im = _plot_rank(axes[i], hafter_map[field][tempsuffix], "%d" % tempsuffix,
                                    tempH, tempX, tempY)

            if i == 0: 
                axes[i].set_ylabel(ylabel)
            axes[i].set_xlabel(xlabel)

            fig.colorbar(im[3], ax=axes[i])

        
        field_name = fos_infos[fos_infos['field_id'] == field].iloc[0, -1]
            
        fig.suptitle(field_name)
        fig.tight_layout()
        fig.savefig('outputs/fos_hist2d_rank_%s_%s_temporal.pdf' % (outname, field_name))
        fig.show()

if __name__ == '__main__':
    
    # hafter_map = hindex_before_after_temporal(_hindex_before_after_temporal, 'hindex')
    citsafter_map = hindex_before_after_temporal(_cits_before_after_temporal, 'cits')
    papersafter_map = hindex_before_after_temporal(_papers_before_after_temporal, 'papers')


    # ylabel = 'author\'s rank by h-index\n excluding their main collaborator'
    # xlabel = 'author\'s rank by citations'
    # outname = 'hindex'
    # plot_rank_temporal(hafter_map, _plot_rank_temporal, xlabel, ylabel, outname)

    ylabel = 'author\'s rank by citations\n excluding their main collaborator'
    xlabel = 'author\'s rank by citations'
    outname = 'cits'
    plot_rank_temporal(citsafter_map, _plot_rank_cits, xlabel, ylabel, outname)

    ylabel = 'author\'s rank by papers\n excluding their main collaborator'
    xlabel = 'author\'s rank by papers'
    outname = 'papers'
    plot_rank_temporal(papersafter_map, _plot_rank_papers, xlabel, ylabel, outname)