# # # Distribution Statement A. Approved for public release. Distribution unlimited.
# # # 
# # # Author:
# # # Naval Research Laboratory, Marine Meteorology Division
# # # 
# # # This program is free software:
# # # you can redistribute it and/or modify it under the terms
# # # of the NRLMMD License included with this program.
# # # 
# # # If you did not receive the license, see
# # # https://github.com/U-S-NRL-Marine-Meteorology-Division/
# # # for more information.
# # # 
# # # This program is distributed WITHOUT ANY WARRANTY;
# # # without even the implied warranty of MERCHANTABILITY
# # # or FITNESS FOR A PARTICULAR PURPOSE.
# # # See the included license for more details.

''' Reader to read a grannual NOAA ATMS SDR TBs in h5 format 
    Output variables in xarray object for geoips processing system
    
    V0:   August 25, 2021
  
    The date is generated by the NOAA community satellite processing package (CSPP), developed at CIMSS
 
    Example of ATMS file names:
    'SATMS_j01_d20210809_t0959306_e1000023_b19296_fnmoc_ops.h5': SDR TBs variables
    'GATMO_j01_d20210809_t0959306_e1000023_b19296_fnmoc_ops.h5'  SDR Geolocation variables

    TB[12,96,22]:  for each granuel

    CHAN#  Center-Freq(GHz)  POL             
    1      23.8               V
    2      31.4               V
    3      50.3               H
    4      51.76              H
    5      52.8               H
    6      53.596+-0.115      H
    7      54.4               H
    8      54.94              H
    9      55.5               H
    10     57.290(f0)         H
    11     f0 +-0.217         H
    12     f0 +-0.322+-0.048  H
    13     f0 +-0.322+-0.022  H
    14     f0 +-0.322+-0.010  H
    15     f0 +-0.322+-0.0045 H

    16     88.2               V
    17     165.5              H
    18     183.1+-7           H
    19     183.1+-4.5         H    (FNMOC used this chan for 183 GHz image)
    20     183.1+-3.0         H
    21     183.1+-1.8         H
    22     183.1+-1.0         H

    BeamTime[12,96]:  microsecond, i.e., 1*10^-6.  IET "IDPS Epoch Time" is used.  
                      It is a signed 64-bit integer giving microseconds since 00:00:00.000000 Jan 1 1958. 
    BrightnessTemperatureFactors[2]: 1: scale (unitless); 2: offset (K)     
    BrightnessTemperature[12,96,22]: [scan,pix,chans]     
 
    SDR geolocation Info
    Latitude/Longitude[12,96]:   for Chan 17 only (for initial product, it is used for all channels.
    BeamLatitude[12,96,5]:       for chan 1,2,3,16,17. They will be used for associated TBs at a later date.
    BeamLongitude[12,96,5]:      for chan 1,2,3,16,17 
    SatelliteAzimuthAngle, SatelliteZenithAngle, SolarAzimuthAngle, SolarZenithAngle[12,96]

    Note:  Unix epoch time is defined as the number of seconds that have elapsed since January 1, 1970 (midnight UTC/GMT).
           Thus, there is a 12 years difference for the JPSS data when datetime.datetime.utcfromtimestamp(epoch) is used
           to convert the JPSS IDPS Epoch time to the humman-readable date.   

This reader is developed to read one granual a time from ATMS npp and jpss-1(n20) data files.
The example files are:  
SATMS_j01_d20210809_t0959306_e1000023_b19296_fnmoc_ops.h5:     for TBs.  'b': orbit#
GATMO_j01_d20210809_t0959306_e1000023_b19296_fnmoc_ops.h5:     for geolocations
 
'''

# Python Standard Libraries

from os.path import basename

import h5py
import numpy as np

import logging
LOG = logging.getLogger(__name__)
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt

reader_type = 'standard'

#from IPython import embed as shell

# list of variables selected from input files
atms_vars=['BrightnessTemperature','BrightnessTemperatureFactors','BeamTime','Latitude', 'Longitude',
           'SatelliteAzimuthAngle','SatelliteZenithAngle', 'SolarAzimuthAngle', 'SolarZenithAngle',
           'StartTime']

# unify common names for sat/sun-zenith and azimuth angles
xvarnames={'SolarZenithAngle': 'SunZenith',
           'SolarAzimuthAngle': 'SunAzimuth',
           'SatelliteZenithAngle': 'SatZenith',
           'SatelliteAzimuthAngle': 'SatAzimuth'}

import xarray as xr
final_xarray = xr.Dataset()              #define a xarray to hold all selected variables


def read_atms_file(fname, xarray_atms):
    fileobj = h5py.File(fname, mode='r')
    import pandas as pd
    import xarray as xr
    import numpy
    import datetime
 
    #check for available variables from nput file
    if 'ATMS-SDR_All' in fileobj['All_Data'].keys():                 #for TB-data
        data_select=fileobj['All_Data']['ATMS-SDR_All']
        
        tb      = data_select['BrightnessTemperature'][()] 
        tb_time = data_select['BeamTime'][()] 
        tb_factor = data_select['BrightnessTemperatureFactors'][()]

        # convert tb to actual values
        tbs=tb*tb_factor[0] + tb_factor[1]
 
        # TBs for selected channels 
        V23 =tbs[:,:,0]
        V31 =tbs[:,:,1]
        H50 =tbs[:,:,2]
        V89 =tbs[:,:,15]
        H165=tbs[:,:,16]    
        H183=tbs[:,:,18]                  #to match the 183+-4.5 GHz channel used by FNMOC    

        #  get UTC time in datetime64 format required by geoips for each pixel
        nscan=tb_time.shape[0]        # 12
        npix =tb_time.shape[1]        # 96 pixels per scan
        time_scan=np.zeros((nscan,npix)).astype('int')   # 0 initilization of an integer array     

        for i in range(nscan):
            for j in range(npix):
                pix_date=datetime.datetime.utcfromtimestamp(tb_time[i,j]/1e6).replace(tzinfo=datetime.timezone.utc)

                yy   = pix_date.year
                mo   = pix_date.month
                dd   = pix_date.day
                hh   = pix_date.hour
                mm   = pix_date.minute
                ss   = pix_date.second

                # setup time in datetime64 format required by geoips 
                yy=yy-12   #adjust difference of Unix epoch (1970) and JPSS IDPS epoch (19598)=378,691,200 seconds  
                time_scan[i,j]='%04d%02d%02d%02d%02d%02d' % (yy,mo,dd,hh,mm,ss)

        #make list of numpy arrays
        var_names=[V23,V31,H50,V89,H165,H183,time_scan]
        list_vars = ['V23','V31','H50','V89','H165','H183','time_scan']

    if 'ATMS-SDR-GEO_All' in fileobj['All_Data'].keys():             #for geo-data
        data_select=fileobj['All_Data']['ATMS-SDR-GEO_All']

        lat       =data_select['Latitude'][()]
        lon       =data_select['Longitude'][()]
        SunZenith =data_select['SolarZenithAngle'][()]
        SunAzimuth=data_select['SolarAzimuthAngle'][()]
        SatZenith =data_select['SatelliteZenithAngle'][()]
        SatAzimuth=data_select['SatelliteAzimuthAngle'][()]        

        #make list of numpy arrays
        var_names=[lat,lon,SunZenith,SunAzimuth,SatZenith,SatAzimuth]
        list_vars = ['latitude','longitude','SunZenith','SunAzimuth','SatZenith','SatAzimuth']

    #close the h5 object
    fileobj.close()

    #          ------  setup xarray variables   ------

    #namelist_atms  = ['latitude', 'longitude', 'V23', 'V31', 'H50','V89','H165','H183','timestamp'
    #                   'SunZenith', 'SunAzimuth', 'SatZenith','SatAzimuth']

    if list_vars[0] not in xarray_atms.variables.keys():
        # new variables, add these vars to the ATMS xarray
        for i in range(len(list_vars)):
            if list_vars[i] == 'time_scan':
                final_xarray['timestamp']=xr.DataArray(pd.DataFrame(var_names[i]).apply(pd.to_datetime,format='%Y%m%d%H%M%S'))
            else:
                final_xarray[list_vars[i]] =xr.DataArray(var_names[i])
    else:
        # accumulation of mutliple files
        for i in range(len(list_vars)):
            if list_vars[i] == 'time_scan':
                new_timestamp = xr.DataArray(pd.DataFrame(var_names[i]).apply(pd.to_datetime, format='%Y%m%d%H%M%S'))
                merged_array=numpy.vstack([xarray_atms['timestamp'].to_masked_array(), new_timestamp.to_masked_array()])
                final_xarray['timestamp'] = xr.DataArray(merged_array,dims=['dim_'+str(merged_array.shape[0]), 'dim_1'])
            else:
                merged_array=numpy.vstack([xarray_atms[list_vars[i]].to_masked_array(), var_names[i]])
                final_xarray[list_vars[i]] = xr.DataArray(merged_array,dims=['dim_'+str(merged_array.shape[0]), 'dim_1'])

    
    return final_xarray


def atms_hdf5(fnames, metadata_only=False, chans=None, area_def=None, self_register=False):

    ''' Read ATMS  hdf5 data products.

    All GeoIPS 2.0 readers read data into xarray Datasets - a separate
    dataset for each shape/resolution of data - and contain standard metadata information.

    Args:
        fnames (list): List of strings, full paths to files
        metadata_only (Optional[bool]):
            * DEFAULT False
            * return before actually reading data if True
            * note:  since atms reader is designed to read all data information from the first time,
                     the second time to read the atms datafiles is not needed.  Thus, reading the data for the second time is skipped
        chans (Optional[list of str]):
            * NOT YET IMPLEMENTED
                * DEFAULT None (include all channels)
                * List of desired channels (skip unneeded variables as needed)
        area_def (Optional[pyresample.AreaDefinition]):
            * NOT YET IMPLEMENTED
                * DEFAULT None (read all data)
                * Specify region to read
        self_register (Optional[str]):
            * NOT YET IMPLEMENTED
                * DEFAULT False (read multiple resolutions of data)
                * register all data to the specified resolution.

    Returns:
        list of xarray.Datasets: list of xarray.Dataset objects with required
            Variables and Attributes: (See geoips/docs :doc:`xarray_standards`)
            
    '''

    import os
    from datetime import datetime
    import numpy as np
    import xarray as xr
    from IPython import embed as shell

    LOG.info('Reading files %s', fnames)

    if metadata_only == True:                      # read-in datafiles first time if 'metadata_only= True'
        xarray_atms = xr.Dataset()
        original_source_filenames = []
        for fname in fnames:
            xarray_atms = read_atms_file(fname, xarray_atms)
            original_source_filenames += [basename(fname)]     # name of last file from input files
        xarray_atms.attrs['original_source_filenames'] = original_source_filenames

        # setup attributors
        fileobj = h5py.File(fname, mode='r')
        from geoips.xarray_utils.timestamp import get_datetime_from_datetime64
        from geoips.xarray_utils.timestamp import get_max_from_xarray_timestamp, get_min_from_xarray_timestamp
        xarray_atms.attrs['start_datetime'] = get_min_from_xarray_timestamp(xarray_atms, 'timestamp')
        xarray_atms.attrs['end_datetime'] = get_max_from_xarray_timestamp(xarray_atms, 'timestamp')
        xarray_atms.attrs['source_name'] = 'atms'
        xarray_atms.attrs['platform_name'] = fileobj.attrs['Platform_Short_Name'][0,0].decode("utf-8")  #could be changed if needed
        xarray_atms.attrs['data_provider'] = 'NOAA'      

        # MTIFs need to be "prettier" for PMW products, so 2km resolution for final image
        xarray_atms.attrs['sample_distance_km'] = 2
        xarray_atms.attrs['interpolation_radius_of_influence'] = 30000     #could be tuned if needed
        fileobj.close()
    else:                   # if 'metadata_only= False', it is for the second time to read-in datafiles    
        xarray_atms=final_xarray                 #avoid read the data the second time

    return {'METADATA': xarray_atms[[]],
            'ATMS': xarray_atms}
