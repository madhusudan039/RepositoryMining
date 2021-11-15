#Modules required for the program
import json
from selenium import webdriver
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import Options
import re
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
import statistics as stats

# Definition of repoMining class
class repoMining:
    def __init__(self, chrome_driver_address, debug=False):
        chrome_options = Options()
        chrome_options.add_argument("--use-fake-ui-for-media-stream")
        chrome_options.add_argument("--disable-user-media-security=true")
        chrome_options.add_argument('headless')
        
        self.driver = webdriver.Chrome(chrome_driver_address,options=chrome_options)
        
        # Configuring whether output messages will be printed for debugging purpose
        self.debug = debug
    
    # Function to get all the sub-directories or modules under a directory
    def getModules(self, url):
        module_list = []
        try:
            self.driver.get(url)
            content = self.driver.page_source
            soup = BeautifulSoup(content,'html.parser')
        except:
            if self.debug == True:
                print('Cannot Process URL: ',url)
            return []

        for element in soup.body.findAll('div',attrs={"class":"Box mb-3"}):
            for level1 in element.findAll('div', attrs={"role":"row"}):
                for tag in level1.findAll('div', attrs={"role":"rowheader"}):
                    text = tag.get_text().strip()
                    if self.debug == True:
                        print('Text: '+text)

                    link = tag.find('a', href=True)
                    url = link['href']
                    if self.debug == True:
                        print("URL: "+url)

                    if "tree" in url:
                        url_split = url.split('/')
                        module = url_split[-2] +'/'+url_split[-1]
                        module_list.append(module)

        return module_list

    # getDuration takes a string with commit date, processes the date and returns the difference (in number of days) between
    # the processed date and current date
    def getDuration(self, str):
        str2 = str.split()
        str = str2[-3]+" "+str2[-2]+" "+str2[-1]
        commit_datetime = datetime.strptime(str, '%b %d, %Y')
        duration = datetime.now() - commit_datetime
        return duration.days

    # mapCommitInfo function collects the all commit and churn infomation of all the files under the root directory (nova/nova here)
    # considering the history log of the root directory. During information collection, only the history within the specified number of days
    # are considered. No module to file mapping is done here.
    def mapCommitInfo(self, url, github_prefix, number_of_days):
        commit_dict = {}
        content = None
        content2 = None
        soup = None
        soup2 = None
        is_loop =True
        # Loop to traverse pages one by one
        while is_loop == True: 
            is_loop = False
            
            try:
                self.driver.delete_all_cookies()
                self.driver.get(url)
                content = self.driver.page_source
                soup = BeautifulSoup(content,'html.parser')
            except:
                if self.debug == True:
                    print('Cannot Process URL: ',url)
                return commit_dict, 1

            is_next_page = True
            # Finding commits of a day
            for element in soup.body.findAll('div',attrs={"class":"TimelineItem-body"}):
                header = element.find('h2')
                if header is None:
                    continue
                header_info = header.get_text()
                    
                if int(self.getDuration(header_info)) <= number_of_days:
                    if self.debug == True:
                        print("Header Information: "+ header_info)
                    print('============= Commits from ',self.getDuration(header_info), " days ago =============")
                    # Getting all of a commits of a day with corresponding messages
                    for link_tag in element.findAll('li'):
                        commit_message = link_tag.find('p')
                        if commit_message is None:
                            continue
                        commit_message = commit_message.get_text().strip()
                        if self.debug == True:
                            print(commit_message)
                            
                        # Retrieving the url of the commit
                        commit_info_url = link_tag.find('a',href=True)
                        if commit_info_url is None:
                            continue
                        commit_info_url= commit_info_url['href']
                        commit_info_url = github_prefix + commit_info_url
                        
                        # Fetching commit and churn info from the commit url
                        if self.debug == True:
                            print("Link: ", commit_info_url)
                        try:
                            self.driver.delete_all_cookies()
                            
                            self.driver.get(commit_info_url)
                            content2 = self.driver.page_source
                            soup2 = BeautifulSoup(content2,'html.parser')
                        except:
                            if self.debug == True:
                                print('Cannot Process URL: ',url)
                            return commit_dict, 2

                        # Retrieving file level changes (churns) info
                        element_i=soup2.body.find('div',attrs={"id":"toc"})
                        if element_i is None:
                            continue
                        for li_info in element_i.findAll('li'):
                            li_list = li_info.get_text().strip().split()
                            if self.debug == True:
                                print('li_info: ', li_list)

                            if len(li_list)!=3:
                                continue
                            pattern = '\d+'
                            if len(re.findall(pattern, li_list[0]))>0:
                                pos_count = int(re.findall(pattern, li_list[0])[0])
                            if len(re.findall(pattern, li_list[1]))>0:
                                neg_count = int(re.findall(pattern, li_list[1])[0])
                            file_name = li_list[2]
                            if self.debug == True:
                                print(pos_count, neg_count, file_name)
                            if file_name not in commit_dict:
                                commit_dict[file_name] = []
                            commit_dict[file_name].append((pos_count, neg_count))
                else:
                    return commit_dict, 0

            # Retrieving the next page url (if any)
            element_older_page= soup.body.find('div',attrs={"class":"paginate-container"})
            if element_older_page is None:
                continue
            for tag in element_older_page.findAll('a', href=True):
                if tag.get_text() == "Older":
                    url = tag['href']
                    print("==== Older URL====", url)
                    is_loop = True
                    break

        return commit_dict, 0
    
    # reduceCommitInfo aggregates the commit and churn information from file level to module level
    def reduceCommitInfo(self, commit_dict, module_list):
        commit_count_dict = {}
        churn_count_dict = {}
        for module in module_list:
            commit_count_dict[module] = 0
            churn_count_dict[module] = 0
            
        for file, commit_list in commit_dict.items():
            commit_count = len(commit_list)
            churn_count = 0
            for pos_count, neg_count in commit_list:
                churn_count = churn_count + pos_count + neg_count
            
            for module in module_list:
                if file.startswith(module)==True:
                    commit_count_dict[module] += commit_count
                    churn_count_dict[module] += churn_count
                    break
        return commit_count_dict, churn_count_dict
    
    # printAndSave prints and saves the top k information for a dictionary (same function can be used for both commit info and churn info)
    def printAndSave(self, topK, count_dict, count_type):
        sorted_dict = dict(sorted(count_dict.items(), key=lambda item: item[1], reverse=True))
        with open('Top '+str(topK)+' '+count_type+' info','w', encoding="utf-8") as f:
            index = 1
            for key, value in sorted_dict.items():
                print('Rank '+str(index)+' :'+key+' with '+str(value) +' '+count_type+'s')
                f.write('Rank '+str(index)+' :'+key+' with '+str(value) +' '+count_type+'s\n')
                index += 1
                if index > topK:
                    break
                    
# This function retrieves information from files and generate corresponding graphs                   
def generateGraphs(commit_dict_file, temp_churn_file, temp_commit_file):
    commit_dict = {}
    commit_count_dict = {}
    churn_count_dict = {}
    with open(commit_dict_file,'r', encoding="utf-8") as fv:
        commit_dict=json.load(fv)

    with open(temp_commit_file,'r', encoding="utf-8") as tf:
        commit_count_dict = json.load(tf)
    with open(temp_churn_file,'r', encoding="utf-8") as tf:
        churn_count_dict = json.load(tf)

    fig = plt.figure()
    ax = fig.add_axes([0.15,0.3,0.8,0.65])
    x_values = [k.split('/')[1] for k in commit_count_dict.keys()]
    y_values = [v for v in commit_count_dict.values()]
    sns.barplot(x=x_values,y=y_values)
    plt.xticks(rotation='vertical')
    plt.ylabel('# of commits')
    plt.xlabel('Modules')
    plt.show()
    fig.savefig('Module-wise commit distribution.pdf')
    plt.close()

    fig = plt.figure()
    ax = fig.add_axes([0.15,0.3,0.8,0.65])
    x_values = [k.split('/')[1] for k in churn_count_dict.keys()]
    y_values = [v for v in churn_count_dict.values()]
    # ax.bar(x_values,y_values)
    sns.barplot(x=x_values,y=y_values)
    plt.xticks(rotation='vertical')
    plt.ylabel('# of churns')
    plt.xlabel('Modules')
    plt.show()
    fig.savefig('Module-wise churn distribution.pdf')
    plt.close()

    fig = plt.figure()
    ax = fig.add_axes([0.15,0.15,0.8,0.8])
    file_level_commit_list = [len(v) for v in commit_dict.values()]
    sns.histplot(file_level_commit_list, kde=True, binwidth=(max(file_level_commit_list)-min(file_level_commit_list))/25, color='r',)
    plt.ylabel('# of files')
    plt.xlabel('# of commits')
    plt.show()
    fig.savefig('File level commit distribution.pdf')
    plt.close()

    fig = plt.figure()
    ax = fig.add_axes([0.15,0.15,0.8,0.8])
    file_level_churn_list = [x+y for vl in commit_dict.values() for x, y in vl]
    sns.histplot(file_level_churn_list, ax=ax, kde=True, binwidth=(max(file_level_churn_list)-min(file_level_churn_list))/25, color='r')
    # sns.distplot(file_level_churn_list, kde=True, color='r')
    plt.ylabel('# of files')
    plt.xlabel('# of churns')
    plt.show()
    fig.savefig('File level churn distribution.pdf')
    plt.close()

# This function retrieves information from files and generate corresponding statistics (median and median absolute deviation)       
def generateStat(commit_dict_file, temp_churn_file, temp_commit_file):
    commit_dict = {}
    commit_count_dict = {}
    churn_count_dict = {}
    all_data = []
    with open(commit_dict_file,'r', encoding="utf-8") as fv:
        commit_dict=json.load(fv)

    with open(temp_commit_file,'r', encoding="utf-8") as tf:
        commit_count_dict = json.load(tf)
    with open(temp_churn_file,'r', encoding="utf-8") as tf:
        churn_count_dict = json.load(tf)
        
    commit_data = [value for value in commit_count_dict.values()]
    commit_median = stats.median(commit_data)
    commit_mad = sum([abs(value-commit_median) for value in commit_data])/len(commit_data)
    print("Median of Commit Count: ", commit_median)
    print("Median Absolute Deviation of Commit Count:", commit_mad)
    
    churn_data = [value for value in churn_count_dict.values()]
    churn_median = stats.median(churn_data)
    churn_mad = sum([abs(value-churn_median) for value in churn_data])/len(churn_data)
    print("Median of Churn Count: ",churn_median)
    print("Median Absolute Deviation of Churn Count:",churn_mad)
     
    
def main():
    # A compatible chromedriver need to be downloaded and placed in a folder. Moreover, the path to the 
    # chromedriver need to specified as following
    # In windows
    chrome_driver_address = "C:/chromedriver_win32/chromedriver"
    # In linux
    # chrome_driver_address = "/usr/bin/chromedriver"
    github_prefix = "https://github.com/"
    main_url = "https://github.com/openstack/nova/tree/master/nova"
    commit_dict_file = 'temp_commit_dict.json'
    temp_churn_file = 'temp_churn_count.json'
    temp_commit_file = 'temp_commit_count.json'
    topK = 12
    number_of_days = 180
    commit_url = "https://github.com/openstack/nova/commits/master/nova"
    
    rm = repoMining(chrome_driver_address= chrome_driver_address, debug=False)
    module_list = rm.getModules(main_url)
    print(module_list)

    commit_dict, is_problem = rm.mapCommitInfo(commit_url, github_prefix, number_of_days)
    print(commit_dict)
    with open(commit_dict_file,'w', encoding="utf-8") as cf:
            json.dump(commit_dict, cf)
    if is_problem != 0:
        print('Problem in crawling pages')
        return
    
    commit_count_dict, churn_count_dict = rm.reduceCommitInfo(commit_dict, module_list)
    
    with open(temp_commit_file,'w', encoding="utf-8") as tf:
            json.dump(commit_count_dict, tf)
    with open(temp_churn_file,'w', encoding="utf-8") as tf:
            json.dump(churn_count_dict, tf)
            
    total_commits = sum([v for v in commit_count_dict.values()])
    total_churns = sum([v for v in churn_count_dict.values()])  
    
    print(commit_count_dict, churn_count_dict)
    print("Total number of commits: ", total_commits)
    print("Total number of churns: ", total_churns)
    
    rm.printAndSave(topK,commit_count_dict,'commit')
    rm.printAndSave(topK,churn_count_dict,'churn')

    generateGraphs(commit_dict_file, temp_churn_file, temp_commit_file)
    generateStat(commit_dict_file, temp_churn_file, temp_commit_file)
    
if __name__=="__main__":
    main()