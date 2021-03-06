#!/usr/local/bin/python3

from datetime import datetime, timedelta
import httplib2
# import sys
import plotly.plotly as py
import plotly.graph_objs as go

from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow


# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret. You can acquire an OAuth 2.0 client ID and client secret from
# the {{ Google Cloud Console }} at {{ https://cloud.google.com/console }}.
# Please ensure that you have enabled the YouTube Data and YouTube Analytics APIs for your project.
# For more information about using OAuth2 to access the YouTube Data API, see: https://developers.google.com/youtube/v3/guides/authentication
# For more information about the client_secrets.json file format, see: https://developers.google.com/api-client-library/python/guide/aaa_client_secrets

# list used to loop through the client_secrets_files to authenticate and get analytics report
countries = ["AU", "AR", "BR", "DE", "FR", "IT", "MX", "NL", "PL", "QC", "RU", "UK"]


class AuthenticatedQueries(object):
    '''
    authenticate to youtube data api and youtube analytics api with oauth2,
    get and return an analytics query response
    '''

    youtube_api_service_name = "youtube"
    youtube_api_version = "v3"
    youtube_analytics_api_service_name = "youtubeAnalytics"
    youtube_analytics_api_version = "v1"

    def __init__(self):
        self.now = datetime.now()
        self.one_day_ago = (self.now - timedelta(days=1)).strftime("%Y-%m-%d")
        self.alltime = "2011-01-01"

        self.secrets_files = {
            "AU": "../credentials/client_ids/client_id_AU.json",
            "AR": "../credentials/client_ids/client_id_AU.json",
            "BR": "../credentials/client_ids/client_id_BR.json",
            "DE": "../credentials/client_ids/client_id_DE.json",
            "FR": "../credentials/client_ids/client_id_FR.json",
            "IT": "../credentials/client_ids/client_id_IT.json",
            "MX": "../credentials/client_ids/client_id_MX.json",
            "NL": "../credentials/client_ids/client_id_NL.json",
            "PL": "../credentials/client_ids/client_id_PL.json",
            "QC": "../credentials/client_ids/client_id_QC.json",
            "RU": "../credentials/client_ids/client_id_RU.json",
            "UK": "../credentials/client_ids/client_id_UK.json"
        }

        self.scopes = ["https://www.googleapis.com/auth/youtube.readonly",
                       "https://www.googleapis.com/auth/yt-analytics.readonly",
                       # "https://www.googleapis.com/auth/yt-analytics-monetary.readonly"
                       ]

    def get_authenticated_services(self, oauth_file_path):
        # This variable defines a message to display if the CLIENT_SECRETS_FILE is missing.
        missing_clients_secrets_message = """
        WARNING: Please configure OAuth 2.0

        To make this run you will need to populate the client_secrets.json file
        found at:

           {}

        with information from the {{ Cloud Console }}
        {{ https://cloud.google.com/console }}

        For more information about the client_secrets.json file format, please visit:
        https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
        """.format(self.secrets_files[oauth_file_path])

        flow = flow_from_clientsecrets(self.secrets_files[oauth_file_path],
                                       scope=" ".join(self.scopes),
                                       message=missing_clients_secrets_message)

        # TODO: make this more generic by not using script name to make file name
        storage = Storage("../credentials/oaths/{}-{}-oauth2.json".format("analytics_test_multiple_channel.py", oauth_file_path))
        credentials = storage.get()

        if credentials is None or credentials.invalid:
            credentials = run_flow(flow, storage, self.args)

        http = credentials.authorize(httplib2.Http())

        self.youtube = build(self.youtube_api_service_name, self.youtube_api_version, http=http)
        self.youtube_analytics = build(self.youtube_analytics_api_service_name, self.youtube_analytics_api_version, http=http)

    def get_channel_id(self):
        self.channels_list_response = self.youtube.channels().list(mine=True, part="id").execute()

        self.channel_id = self.channels_list_response["items"][0]["id"]

    def run_analytics_report(self, params):
        '''
        Call the Analytics API to retrieve a report. For a list of available reports,
        see: https://developers.google.com/youtube/analytics/v1/channel_reports
        '''
        self.analytics_query_response = self.youtube_analytics.reports().query(
            ids="channel=={}".format(self.channel_id),
            metrics=params,
            start_date=self.alltime,
            end_date=self.one_day_ago,
            alt="json",
            sort="-views"
        ).execute()

        return self.analytics_query_response

    def run_top_10_report(self):
        '''
        Call the Analytics API to retrieve the top 10 videos by views
        '''
        self.top_10_query_response = self.youtube_analytics.reports().query(
            ids="channel==%s" % self.channel_id,
            metrics="views,comments,likes,dislikes,shares",
            dimensions="video",
            start_date=self.alltime,
            end_date=self.one_day_ago,
            max_results=10,
            sort="-views"
        ).execute()

        top_10_list = [[row[0], int(row[1])] for row in self.top_10_query_response.get("rows")]
        top_10_joined = ','.join(item[0] for item in top_10_list)
        videos_list_response = self.youtube.videos().list(id=top_10_joined, part='snippet').execute()

        for i in range(len(top_10_list)):
            top_10_list[i].insert(0, videos_list_response['items'][i]['snippet']['title'])

        self.top_10 = top_10_list

    def print_report(self, country):
        '''
        parses the analytics API query response - which can be JSON or CSV - and prints relevant info.
        need to pass in country here just for cli printing
        '''
        print("ANALYTICS DATA FOR {}'s CHANNEL".format(country))

        for column_header in self.analytics_query_response.get("columnHeaders", []):
            print("{:<20}".format(column_header["name"]), end='')
        print("")

        for row in self.analytics_query_response.get("rows", []):
            for value in row:
                print("{:<20.0f}".format(value), end='')
        print("\n")

    def print_top_10(self):
        print("TOP 10 VIDEOS")
        for item in self.top_10:
            print('{}: {:,}'.format(item[0], item[2]))
        print("\n")


class Analytics(object):
    '''
    hold analytics metrics in a dict in format: {'metric': {'country': integer}}.
    methods to process metrics in various ways, print results, and update plotly graphs
    '''

    def __init__(self):
        self.metrics = {}

    def compute_totals(self):
        for key in self.metrics.keys():
            self.metrics[key]['total'] = sum(value for value in self.metrics[key].values())

    def sort_metrics(self, key):

        return sorted(self.metrics[key].items(), key=lambda x: x[1], reverse=True)

    def print_sorted_metrics(self):
        for key in self.metrics.keys():

            print(key.upper())

            sorted_metrics = self.sort_metrics(key)
            for i in range(len(sorted_metrics)):
                print('{}: {:,}'.format(sorted_metrics[i][0], sorted_metrics[i][1]))

            print('\n')


class Plotter(object):
    '''
    holds functions for updating graphs
    '''

    def __init__(self, metrics):
        self.metrics = metrics

    def sort_metrics(self, key):

        return sorted(self.metrics[key].items(), key=lambda x: x[1], reverse=True)

    def update_views_pie(self):
        print('updating views pie...\n')

        labels = []
        values = []

        for key, value in self.metrics['views'].items():
            if key != 'total':
                labels.append(key)
                values.append(value)

        pie_get = py.get_figure("https://plot.ly/~allrecipes_international/2/")
        data = pie_get.data

        # to construct dict for computing view differences from last update:
        # past_views_dict = {label: value for label, value in zip(data[0]['labels'], data[0]['values'])}

        data.update({'values': values, 'labels': labels})

        py.plot(pie_get, filename='youtube channel views pie', auto_open=False)

    def update_views_graph(self):
        # this function relies on 'total' being a key in the metrics['views'] dict

        print("updating views graph...\n")

        sorted_views = self.sort_metrics('views')
        x = [sorted_views[i][0] for i in range(len(sorted_views)) if sorted_views[i][0] != 'total']
        y = [sorted_views[i][1] for i in range(len(sorted_views)) if sorted_views[i][0] != 'total']
        total_views = 'TOTAL VIEWS: ' + '{:,}'.format(self.metrics['views']['total'])

        views_graph = py.get_figure("https://plot.ly/~allrecipes_international/4/")

        views_graph.data.update({'x': x, 'y': y})
        views_graph.layout.annotations.update({'text': total_views})

        py.plot(views_graph, filename='youtube channel views graph', auto_open=False)

    def update_subscriber_bars(self):
        pass
        '''
        print('updating subscriber bars...\n')

        y_data = countries[:]
        y_data.reverse()

        gained = [self.metrics['subscribersGained'][thing] for thing in y_data]
        lost = [self.metrics['subscribersLost'][thing] for thing in y_data]

        subscriber_bars = py.get_figure('https://plot.ly/~allrecipes_international/16')

        subscriber_bars.data[0].x = gained
        subscriber_bars.data[1].x = lost

        py.plot(subscriber_bars, filename='subscriber bars', auto_open=False)
        '''

    def update_engagement_bars(self):
        # most code taken from horizontal bars graph example page on plotly

        print("updating engagement bars... \n")

        top_labels = ['comments', 'likes', 'dislikes', 'shares']
        colors = ['#8dd3c7', '#bebada', '#fb8072', '80b1d3']

        x_data = []
        x_data_raw = []
        y_data = countries[:] + ['total']
        y_data.reverse()

        for thing in y_data:
            x_data_raw.append([self.metrics[label][thing] for label in top_labels])

        for item in x_data_raw:
            x_data.append([round(quantity / sum(item) * 100) for quantity in item])

        traces = []

        for i in range(0, len(x_data[0])):
            for xd, yd in zip(x_data, y_data):
                traces.append(go.Bar(
                    x=xd[i],
                    y=yd,
                    orientation='h',
                    marker=dict(
                        color=colors[i],
                        line=dict(
                                color='rgb(248, 248, 249)',
                                width=1)
                    )
                ))

        annotations = []

        for yd, xd in zip(y_data, x_data):
            # labeling the y-axis
            annotations.append(dict(xref='paper', yref='y',
                                    x=0.14, y=yd,
                                    xanchor='right',
                                    text=str(yd),
                                    font=dict(family='Arial', size=14,
                                              color='rgb(67, 67, 67)'),
                                    showarrow=False, align='right'))
            # labeling the first percentage of each bar (x_axis)
            annotations.append(dict(xref='x', yref='y',
                                    x=xd[0] / 2, y=yd,
                                    text=str(xd[0]) + '%',
                                    font=dict(family='Arial', size=14,
                                              color='rgb(248, 248, 255)'),
                                    showarrow=False))
            # labeling the first Likert scale (on the top)
            if yd == y_data[-1]:
                annotations.append(dict(xref='x', yref='paper',
                                        x=xd[0] / 2, y=1.1,
                                        text=top_labels[0],
                                        font=dict(family='Arial', size=14,
                                                  color='rgb(67, 67, 67)'),
                                        showarrow=False))
            space = xd[0]
            for i in range(1, len(xd)):
                    # labeling the rest of percentages for each bar (x_axis)
                    annotations.append(dict(xref='x', yref='y',
                                            x=space + (xd[i]/2), y=yd,
                                            text=str(xd[i]) + '%',
                                            font=dict(family='Arial', size=14,
                                                      color='rgb(248, 248, 255)'),
                                            showarrow=False))
                    # labeling the Likert scale
                    if yd == y_data[-1]:
                        annotations.append(dict(xref='x', yref='paper',
                                                x=space + (xd[i]/2), y=1.1,
                                                text=top_labels[i],
                                                font=dict(family='Arial', size=14,
                                                          color='rgb(67, 67, 67)'),
                                                showarrow=False))
                    space += xd[i]

        engagement_graph = py.get_figure('https://plot.ly/~allrecipes_international/10')
        layout = engagement_graph.layout
        layout['annotations'] = annotations

        fig = go.Figure(data=traces, layout=layout)
        py.plot(fig, filename='engagement bars', auto_open=False)


if __name__ == "__main__":

    authenticated_queries = AuthenticatedQueries()

    # create a list of the metric names for the analytics report
    # the order of these in column_headers doesn't matter because the metric names are keys in the metrics dict
    metrics_query = "views,comments,likes,dislikes,shares,subscribersGained,subscribersLost"
    column_headers = metrics_query.split(',')

    analytics = Analytics()
    analytics.metrics = {column: {} for column in column_headers}

    for country in countries:

        authenticated_queries.get_authenticated_services(country)

        try:
            authenticated_queries.get_channel_id()
            report = authenticated_queries.run_analytics_report(metrics_query)
            authenticated_queries.print_report(country)

            authenticated_queries.run_top_10_report()
            authenticated_queries.print_top_10()

            # update dicts in metrics with country specific values
            for i in range(len(column_headers)):
                analytics.metrics[column_headers[i]][country] = int(report['rows'][0][i])

        except HttpError as e:
            print("An HTTP error {} occurred:".format(e.resp.status))
            print("{}".format(e.content))

    analytics.compute_totals()
    plotter = Plotter(analytics.metrics)

    try:
        pass
        # plotter.update_views_pie()
        # plotter.update_views_graph()
        # plotter.update_engagement_bars()
        # plotter.update_subscriber_bars()

    except Exception as e:
        print(e)

    analytics.print_sorted_metrics()
