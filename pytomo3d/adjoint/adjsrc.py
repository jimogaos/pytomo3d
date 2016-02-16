#!/usr/bin/env python
import os
import yaml
import numpy as np
from obspy import Stream, Trace
from obspy.core.util.geodetics import gps2DistAzimuth
import pyadjoint
from pyadjoint import AdjointSource


def plot_adjsrc_figure(figure_dir, figure_id, adjsrc, _verbose=False,
                       figure_format="pdf"):
    """
    Plot adjoint source figure

    :param figure_dir: output figured directory
    :type figure_dir: str
    :param figure_id: figure id, for example, you can use trace id
        as figure_id, like "II.AAK.00.BHZ"
    :type figure_id: str
    :param adjsrc: adjoint source
    :type adjsrc: pyadjoint.AdjointSource
    :param _verbose: output verbose flag
    :type _verbose: bool
    :param figure_format: output figure format, for example, "pdf"
        or "png"
    :return:
    """
    outfn = "%s.%s" % (figure_id, figure_format)
    figfn = os.path.join(figure_dir, outfn)
    if _verbose:
        print "Output fig:", figfn
    adjsrc.plot(figfn)


def _stats_channel_window(windows):
    """
    Determine number of windows on each channel of each component.
    """
    channel_win_dict = dict()
    for chan_win in windows:
        chan_id = chan_win[0].channel_id
        nwin = len(chan_win)
        channel_win_dict[chan_id] = nwin

    return channel_win_dict


def _clean_adj_results(chan_adj_dict, chan_nwin_dict):
    """
    Remove chan from channel_nwins_dict if the key is not in
    channel_adj_dict, for clean purpose.
    """
    clean_adj_dict = {}
    clean_nwin_dict = {}
    for chan_id, chan_adj in chan_adj_dict.iteritems():
        clean_adj_dict[chan_id] = chan_adj
        clean_nwin_dict[chan_id] = chan_nwin_dict[chan_id]

    return clean_adj_dict, clean_nwin_dict


def load_adjoint_config_yaml(filename):
    """
    load yaml and setup pyadjoint.Config object
    """
    with open(filename) as fh:
        data = yaml.load(fh)

    if data["min_period"] > data["max_period"]:
        raise ValueError("min_period is larger than max_period in config "
                         "file: %s" % filename)

    return pyadjoint.Config(**data)


def calculate_adjsrc_on_trace(obs, syn, windows, config, adj_src_type,
                              adjoint_src_flag=True, plot_flag=False):
    """
    Calculate adjoint source on a pair of trace and windows selected

    :param obs: observed trace
    :type obs: obspy.Trace
    :param syn: synthetic trace
    :type syn: obspy.Trace
    :param windows: windows information, 2-dimension array, like
        [[win_1_left, win_1_right], [win_2_left, win_2_right], ...]
    :type windows: list or numpy.array
    :param config: config of pyadjoint
    :type config: pyadjoint.Config
    :param adj_src_type: adjoint source type, like "multitaper"
    :type adj_src_type: str
    :param adjoint_src_flag: whether calcualte adjoint source or not.
        If False, only make measurements
    :type adjoint_src_flag: bool
    :param plot_flag: whether make plots or not. If True, it will lot
        a adjoint source figure right after calculation
    :type plot_flag:  bool
    :return: adjoint source(pyadjoit.AdjointSource)
    """
    if not isinstance(obs, Trace):
        raise ValueError("Input obs should be obspy.Trace")
    if not isinstance(syn, Trace):
        raise ValueError("Input syn should be obspy.Trace")
    if not isinstance(config, pyadjoint.Config):
        raise ValueError("Input config should be pyadjoint.Config")
    windows = np.array(windows)
    if len(windows.shape) != 2 or windows.shape[1] != 2:
        raise ValueError("Input windows dimension incorrect, dimention"
                         "(*, 2) expected")

    try:
        adjsrc = pyadjoint.calculate_adjoint_source(
            adj_src_type=adj_src_type, observed=obs, synthetic=syn,
            config=config, window=windows, adjoint_src=adjoint_src_flag,
            plot=plot_flag)
    except:
        adjsrc = None

    return adjsrc


def calculate_adjsrc_on_stream(observed, synthetic, windows, config,
                               adj_src_type, plot_flag=False,
                               adjoint_src_flag=True):
    """
    calculate adjoint source on a pair of stream and windows selected

    :param observed: observed stream
    :type observed: obspy.Stream
    :param synthetic: observed stream
    :type synthetic: obspy.Stream
    :param windows: list of pyflex windows, like:
        [[Windows(), Windows(), Windows()], [Windows(), Windows()], ...]
        For each element, it contains windows for one channel
    :type windows: list
    :param config: config for calculating adjoint source
    :type config: pyadjoit.Config
    :param adj_src_type: adjoint source type
    :type adj_src_type: str
    :param plot_flag: plot flag. Leave it to True if you want to see adjoint
        plots for every trace
    :type plot_flag: bool
    :param adjoint_src_flag: adjoint source flag. Set it to True if you want
        to calculate adjoint sources
    :type adjoint_src_flag: bool
    :return:
    """

    channel_adj_dict = {}

    for chan_win in windows:
        if len(chan_win) == 0:
            continue
        obsd_id = chan_win[0].channel_id

        try:
            obs = observed.select(id=obsd_id)[0]
        except:
            raise ValueError("Missing observed trace for window: %s" % obsd_id)

        try:
            syn = synthetic.select(channel="*%s" % obs.stats.channel[-1])[0]
        except:
            raise ValueError("Missing synthetic trace matching obsd id: %s"
                             % obsd_id)

        wins = []
        # read windows for this trace
        for _win in chan_win:
            win_b = _win.relative_starttime
            win_e = _win.relative_endtime
            wins.append([win_b, win_e])
        wins = np.array(wins)

        adjsrc = calculate_adjsrc_on_trace(
            obs, syn, wins, config, adj_src_type,
            adjoint_src_flag=adjoint_src_flag,
            plot_flag=plot_flag)

        if adjsrc is None:
            continue
        channel_adj_dict[obsd_id] = adjsrc

    return channel_adj_dict


def adjsrc_function(observed, synthetic, windows, config,
                    adj_src_type='multitaper_misfit', figure_mode=False,
                    figure_dir=None, _verbose=False):
    """
    Calculate adjoint sources using the time windows selected by pyflex
    and stats the window information at the same time

    :param observed: Observed data for one station
    :type observed: An obspy.core.stream.Stream object.
    :param synthetic: Synthetic data for one station
    :type synthetic: An obspy.core.stream.Stream object
    :param windows: window files for one station, produced by
        FLEXWIN/pyflexwin
    :type windows: a dictionary instance with all time windows for each
        contained traces in the stream object.
    :param config: parameters
    :type config: a class instance with all necessary constants/parameters
    :param adj_src_type: measurement type ("cc_traveltime_misfit",
        "multitaper_misfit", "waveform_misfit")
    :type adj_src_type: str
    """
    if not isinstance(observed, Stream):
        raise ValueError("Input observed should be obspy.Stream")
    if not isinstance(synthetic, Stream):
        raise ValueError("Input synthetic should be obspy.Stream")
    if windows is None or len(windows) == 0:
        return
    if not isinstance(config, pyadjoint.Config):
        raise ValueError("Input config should be pyadjoint.Config")

    channel_nwins_dict = _stats_channel_window(windows)
    channel_adj_dict = \
        calculate_adjsrc_on_stream(observed, synthetic, windows, config,
                                   adj_src_type)

    return _clean_adj_results(channel_adj_dict, channel_nwins_dict)


def calculate_baz(elat, elon, slat, slon):
    """
    Calculate back azimuth

    :param elat: event latitude
    :param elon: event longitude
    :param slat: station latitude
    :param slon: station longitude
    :return: back azimuth
    """

    _, baz, _ = gps2DistAzimuth(elat, elon, slat, slon)

    return baz


def _convert_adj_to_trace(adj, starttime, chan_id):
    """
    Convert AdjointSource to Trace,for internal use only
    """

    tr = Trace()
    tr.data = adj.adjoint_source
    tr.stats.starttime = starttime
    tr.stats.delta = adj.dt

    tr.stats.channel = str(chan_id.split(".")[-1])
    tr.stats.station = adj.station
    tr.stats.network = adj.network
    tr.stats.location = chan_id.split(".")[2]

    return tr


def _convert_trace_to_adj(tr, adj):
    """
    Convert Trace to AdjointSource, for internal use only
    """

    adj.dt = tr.stats.delta
    adj.component = tr.stats.channel[-1]
    adj.adjoint_source = tr.data
    adj.station = tr.stats.station
    adj.network = tr.stats.network
    return adj


def zero_padding_stream(stream, starttime, endtime):
    """
    Zero padding the stream to time [starttime, endtime)
    """
    if starttime > endtime:
        raise ValueError("Starttime is larger than endtime: [%f, %f]"
                         % (starttime, endtime))

    for tr in stream:
        dt = tr.stats.delta
        npts = tr.stats.npts
        tr_starttime = tr.stats.starttime
        tr_endtime = tr.stats.endtime

        npts_before = int((tr_starttime - starttime) / dt) + 1
        npts_before = max(npts_before, 0)
        npts_after = int((endtime - tr_endtime) / dt) + 1
        npts_after = max(npts_after, 0)

        # recalculate the time for padding trace
        padding_starttime = tr_starttime - npts_before * dt
        padding_array = np.zeros(npts_before + npts + npts_after)
        padding_array[npts_before:(npts_before + npts)] = \
            tr.data[:]

        tr.data = padding_array
        tr.stats.starttime = padding_starttime


def sum_adj_on_component(adj_stream, weight_dict):
    """
    Sum adjoint source on different channels but same component
    together, like "II.AAK.00.BHZ" and "II.AAK.10.BHZ" to form
    "II.AAK.BHZ"

    :param adj_stream: adjoint source stream
    :param weight_dict: weight dictionary, should be something like
        {"Z":{"II.AAK.00.BHZ": 0.5, "II.AAK.10.BHZ": 0.5},
         "R":{"II.AAK.00.BHR": 0.3, "II.AAK.10.BHR": 0.7},
         "T":{"II.AAK..BHT": 1.0}}
    :return: summed adjoint source stream
    """
    new_stream = Stream()
    done_comps = []
    for comp, comp_weights in weight_dict.iteritems():
        for chan_id, chan_weight in comp_weights.iteritems():
            if comp not in done_comps:
                done_comps.append(comp)
                comp_tr = adj_stream.select(id=chan_id)[0]
                comp_tr.data *= chan_weight
                comp_tr.stats.location = ""
            else:
                comp_tr.data += \
                    chan_weight * adj_stream.select(id=chan_id)[0].data
        new_stream.append(comp_tr)
    return new_stream


def postprocess_adjsrc(adjsrcs, adj_starttime, raw_synthetic, inventory, event,
                       sum_over_comp_flag=False, weight_dict=None):
    """
    Postprocess adjoint sources to fit SPECFEM input(same as raw_synthetic)
    1) zero padding the adjoint sources
    2) interpolation
    3) add multiple instrument together if there are
    4) rotate from (R, T) to (N, E)

    :param adjsrcs: adjoint sources list from the same station
    :type adjsrcs: list
    :param adj_starttime: starttime of adjoint sources
    :param adj_starttime: obspy.UTCDateTime
    :param raw_synthetic: raw synthetic from SPECFEM output, as reference
    :type raw_synthetic: obspy.Stream or obspy.Trace
    :param inventory: station inventory
    :type inventory: obspy.Inventory
    :param event: event information
    :type event: obspy.Event
    :param sum_over_comp_flag: sum over component flag
    :param weight_dict: weight dictionary
    """

    # extract event information
    origin = event.preferred_origin() or event.origins[0]
    elat = origin.latitude
    elon = origin.longitude
    event_time = origin.time

    # extract station information
    slat = float(inventory[0][0].latitude)
    slon = float(inventory[0][0].longitude)

    # transfer AdjointSource type to stream
    adj_stream = Stream()
    for chan_id, adj in adjsrcs.iteritems():
        _tr = _convert_adj_to_trace(adj, adj_starttime, chan_id)
        adj_stream.append(_tr)

    interp_starttime = raw_synthetic[0].stats.starttime
    interp_delta = raw_synthetic[0].stats.delta
    interp_npts = raw_synthetic[0].stats.npts
    interp_endtime = interp_starttime + interp_delta * interp_npts
    time_offset = interp_starttime - event_time

    # zero padding
    zero_padding_stream(adj_stream, interp_starttime, interp_endtime)

    # interpolate
    adj_stream.interpolate(sampling_rate=1.0/interp_delta,
                           starttime=interp_starttime,
                           npts=interp_npts)

    # sum multiple instruments
    if sum_over_comp_flag:
        if weight_dict is None:
            raise ValueError("weight_dict should be assigned if you want"
                             "to add")
        adj_stream = sum_adj_on_component(adj_stream, weight_dict)

    # add zero trace for missing components
    missinglist = ["Z", "R", "T"]
    tr_template = adj_stream[0]
    for tr in adj_stream:
        missinglist.remove(tr.stats.channel[-1])
    for component in missinglist:
        zero_adj = tr_template.copy()
        zero_adj.data.fill(0.0)
        zero_adj.stats.channel = "%s%s" % (tr_template.stats.channel[0:2],
                                           component)
        adj_stream.append(zero_adj)

    # rotate
    baz = calculate_baz(elat, elon, slat, slon)
    components = [tr.stats.channel[-1] for tr in adj_stream]

    if "R" in components and "T" in components:
        try:
            adj_stream.rotate(method="RT->NE", back_azimuth=baz)
        except Exception as e:
            print e

    # prepare the final results
    final_adjsrcs = []
    _temp_id = adjsrcs.keys()[0]
    adj_src_type = adjsrcs[_temp_id].adj_src_type
    minp = adjsrcs[_temp_id].min_period
    maxp = adjsrcs[_temp_id].max_period
    for tr in adj_stream:
        _adj = AdjointSource(adj_src_type, 0.0, 0.0, minp, maxp, "")
        final_adjsrcs.append(_convert_trace_to_adj(tr, _adj))

    return final_adjsrcs, time_offset