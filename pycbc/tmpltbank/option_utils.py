# Copyright (C) 2013 Ian W. Harry
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import argparse
import textwrap
from pycbc.tmpltbank.lambda_mapping import *
from pycbc import pnutils

class IndentedHelpFormatterWithNL(argparse.ArgumentDefaultsHelpFormatter):
    """
    This class taken from 
    https://groups.google.com/forum/#!topic/comp.lang.python/bfbmtUGhW8I
    and is used to format the argparse help messages to deal with line breaking
    nicer. Specfically the pn-order help is large and looks crappy without this.
    This function is (C) Tim Chase
    """
    def format_description(self, description):
        """
        No documentation
        """
        if not description: return ""
        desc_width = self.width - self.current_indent
        indent = " "*self.current_indent
        # the above is still the same
        bits = description.split('\n')
        formatted_bits = [
            textwrap.fill(bit,
                desc_width,
                initial_indent=indent,
                subsequent_indent=indent)
            for bit in bits]
        result = "\n".join(formatted_bits) + "\n"
        return result

    def format_option(self, option):
        """
        No documentation
        """
        # The help for each option consists of two parts:
        #   * the opt strings and metavars
        #   eg. ("-x", or "-fFILENAME, --file=FILENAME")
        #   * the user-supplied help string
        #   eg. ("turn on expert mode", "read data from FILENAME")
        #
        # If possible, we write both of these on the same line:
        #   -x    turn on expert mode
        #
        # But if the opt string list is too long, we put the help
        # string on a second line, indented to the same column it would
        # start in if it fit on the first line.
        #   -fFILENAME, --file=FILENAME
        #       read data from FILENAME
        result = []
        opts = self.option_strings[option]
        opt_width = self.help_position - self.current_indent - 2
        if len(opts) > opt_width:
            opts = "%*s%s\n" % (self.current_indent, "", opts)
            indent_first = self.help_position
        else: # start help on same line as opts
            opts = "%*s%-*s  " % (self.current_indent, "", opt_width, opts)
            indent_first = 0
        result.append(opts)
        if option.help:
            help_text = self.expand_default(option)
            # Everything is the same up through here
            help_lines = []
            for para in help_text.split("\n"):
                help_lines.extend(textwrap.wrap(para, self.help_width))
            # Everything is the same after here
            result.append("%*s%s\n" % (
                indent_first, "", help_lines[0]))
            result.extend(["%*s%s\n" % (self.help_position, "", line)
                for line in help_lines[1:]])
        elif opts[-1] != "\n":
            result.append("\n")
        return "".join(result)

def insert_metric_calculation_options(parser):
    """
    Adds the options used to obtain a metric in the bank generation codes to an
    argparser as an OptionGroup. This should be used if you want to use these
    options in your code.
    """
    metricOpts = parser.add_argument_group(
                "Options related to calculating the parameter space metric")
    metricOpts.add_argument("--pn-order", action="store", type=str,
                default=None,\
                help="Determines the PN order to use.  For a bank of "
                     "non-spinning templates, spin-related terms in the "
                     "metric will be zero.  REQUIRED. "
                     "Choices: %s" %(pycbcValidOrdersHelpDescriptions))
    metricOpts.add_argument("--f0", action="store", type=float,
                default=70.,\
                help="f0 is used as a dynamic scaling factor when "
                     "calculating integrals used in metric construction.  "
                     "I.e. instead of integrating F(f) we integrate F(f/f0) "
                     "then rescale by powers of f0.  The default value 70Hz "
                     "should be fine for most applications.  OPTIONAL. "
                     "UNITS=Hz. **WARNING: If the ethinca metric is to be "
                     "calculated, f0 must be set equal to f-low**")
    metricOpts.add_argument("--f-low", action="store", type=float,
                default=None,\
                help="Lower frequency cutoff used in computing the "
                     "parameter space metric.  REQUIRED. UNITS=Hz")
    metricOpts.add_argument("--f-upper", action="store", type=float,
                default=None,\
                help="Upper frequency cutoff used in computing the "
                     "parameter space metric.  REQUIRED. UNITS=Hz")
    metricOpts.add_argument("--delta-f", action="store", type=float,
                default=None,
                help="Frequency spacing used in computing the parameter "
                     "space metric:  integrals of the form \int F(f) df "
                     "are approximated as \sum F(f) delta_f.  REQUIRED. "
                     "UNITS=Hz")

def verify_metric_calculation_options(opts, parser):
    """
    Parses the metric calculation options given and verifies that they are
    correct.

    Parameters
    ----------
    opts : argparse.Values instance
        Result of parsing the input options with OptionParser
    parser : object
        The OptionParser instance.
    """
    if not opts.pn_order:
        parser.error("Must supply --pn-order")
    if not opts.f_low:
        parser.error("Must supply --f-low")
    if not opts.f_upper:
        parser.error("Must supply --f-upper")
    if not opts.delta_f:
        parser.error("Must supply --delta-f")

class metricParameters:
    """
    This class holds all of the options that are parsed in the function
    insert_metric_calculation_options
    and all products produced using these options. It can also be initialized
    from the __init__ function, providing directly the options normally
    provided on the command line.
    """
    _psd = None
    _metric = None
    _evals = None
    _evecs = None
    _evecsCV = None
    def __init__(self, pnOrder, fLow, fUpper, deltaF, f0=70):
        """
        Initialize an instance of the metricParameters by providing all
        options directly. See the help message associated with any code
        that uses the metric options for more details of how to set each of
        these, e.g. pycbc_aligned_stoch_bank --help
        """
        self.pnOrder=pnOrder
        self.fLow=fLow
        self.fUpper=fUpper
        self.deltaF=deltaF
        self.f0=f0
        self._moments=None

    @classmethod
    def from_argparse(cls, opts):
        """
        Initialize an instance of the metricParameters class from an
        argparse.OptionParser instance. This assumes that
        insert_metric_calculation_options
        and
        verify_metric_calculation_options
        have already been called before initializing the class.
        """
        return cls(opts.pn_order, opts.f_low, opts.f_upper, opts.delta_f,\
                   f0=opts.f0)

    @property
    def psd(self):
        """
        A pyCBC FrequencySeries holding the appropriate PSD.
        Return the PSD used in the metric calculation.
        """
        if not self._psd:
            errMsg = "The PSD has not been set in the metricParameters "
            errMsg += "instance."
            raise ValueError(errMsg)
        return self._psd

    @psd.setter
    def psd(self, inPsd):
        self._psd = inPsd

    @property
    def moments(self):
        """
        Moments structure
        This contains the result of all the integrals used in computing the
        metrics above. It can be used for the ethinca components calculation,
        or other similar calculations. This is composed of two compound
        dictionaries. The first entry indicates which moment is being
        calculated and the second entry indicates the upper frequency cutoff
        that was used.

        In all cases x = f/f0.

        For the first entries the options are:

        moments['J%d' %(i)][f_cutoff]
        This stores the integral of 
        x**((-i)/3.) * delta X / PSD(x)

        moments['log%d' %(i)][f_cutoff]
        This stores the integral of 
        (numpy.log(x**(1./3.))) x**((-i)/3.) * delta X / PSD(x)

        moments['loglog%d' %(i)][f_cutoff]
        This stores the integral of 
        (numpy.log(x**(1./3.)))**2 x**((-i)/3.) * delta X / PSD(x)

        moments['loglog%d' %(i)][f_cutoff]
        This stores the integral of 
        (numpy.log(x**(1./3.)))**3 x**((-i)/3.) * delta X / PSD(x)

        moments['loglog%d' %(i)][f_cutoff]
        This stores the integral of 
        (numpy.log(x**(1./3.)))**4 x**((-i)/3.) * delta X / PSD(x)

        The second entry stores the frequency cutoff that was used when
        computing the integral.
        """
        return self._moments

    @moments.setter
    def moments(self, inMoments):
        self._moments=inMoments

    @property
    def evals(self):
        """
        The eigenvalues of the parameter space.
        This is a Dictionary of numpy.array
        Each entry in the dictionary corresponds to the different frequency
        ranges described in vary_fmax. If vary_fmax = False, the only entry
        will be f_upper, this corresponds to integrals in [f_low,f_upper). This
        entry is always present. Each other entry will use floats as keys to
        the dictionary. These floats give the upper frequency cutoff when it is
        varying.
        Each numpy.array contains the eigenvalues which, with the eigenvectors
        in evecs, are needed to rotate the
        coordinate system to one in which the metric is the identity matrix.
        """
        if not self._evals:
            errMsg = "The metric eigenvalues have not been set in the "
            errMsg += "metricParameters instance."
            raise ValueError(errMsg)
        return self._evals

    @evals.setter
    def evals(self, inEvals):
        self._evals = inEvals

    @property
    def evecs(self):
        """
        The eigenvectors of the parameter space.
        This is a Dictionary of numpy.matrix
        Each entry in the dictionary is as described under evals.
        Each numpy.matrix contains the eigenvectors which, with the eigenvalues
        in evals, are needed to rotate the
        coordinate system to one in which the metric is the identity matrix.
        """
        if not self._evecs:
            errMsg = "The metric eigenvectors have not been set in the "
            errMsg += "metricParameters instance."
            raise ValueError(errMsg)
        return self._evecs

    @evecs.setter
    def evecs(self, inEvecs):
        self._evecs = inEvecs

    @property
    def metric(self):
        """
        The eigenvectors of the parameter space.
        This is a Dictionary of numpy.matrix
        Each entry in the dictionary is as described under evals.
        Each numpy.matrix contains the metric of the parameter space in the
        Lambda_i coordinate system.
        """
        if not self._metric:
            errMsg = "The metric eigenvectors have not been set in the "
            errMsg += "metricParameters instance."
            raise ValueError(errMsg)
        return self._metric

    @metric.setter
    def metric(self, inMetric):
        self._metric = inMetric

    @property
    def evecsCV(self):
        """
        The eigenvectors of the principal directions of the mu space.
        This is a Dictionary of numpy.matrix
        Each entry in the dictionary is as described under evals.
        Each numpy.matrix contains the eigenvectors which, with the eigenvalues
        in evals, are needed to rotate the
        coordinate system to one in which the metric is the identity matrix.
        """
        if not self._evecsCV:
            errMsg = "The covariance eigenvectors have not been set in the "
            errMsg += "metricParameters instance."
            raise ValueError(errMsg)
        return self._evecsCV

    @evecsCV.setter
    def evecsCV(self, inEvecs):
        self._evecsCV = inEvecs



def insert_mass_range_option_group(parser,nonSpin=False):
    """
    Adds the options used to specify mass ranges in the bank generation codes
    to an argparser as an OptionGroup. This should be used if you
    want to use these options in your code.
 
    Parameters
    -----------
    parser : object
        OptionParser instance.
    nonSpin : boolean, optional (default=False)
        If this is provided the spin-related options will not be added.
    """
    massOpts = parser.add_argument_group("Options related to mass and spin "
                  "limits for bank generation")
    massOpts.add_argument("--min-mass1", action="store", type=float,
                  default=None, 
                  help="Minimum mass1: must be >= min-mass2. "
                       "REQUIRED. UNITS=Solar mass")
    massOpts.add_argument("--max-mass1", action="store", type=float,
                  default=None, 
                  help="Maximum mass1: must be >= max-mass2. "
                       "REQUIRED. UNITS=Solar mass")
    massOpts.add_argument("--min-mass2", action="store", type=float,
                  default=None, 
                  help="Minimum mass2. REQUIRED. UNITS=Solar mass")
    massOpts.add_argument("--max-mass2", action="store", type=float,
                  default=None, 
                  help="Maximum mass2. REQUIRED. UNITS=Solar mass")
    massOpts.add_argument("--max-total-mass", action="store", type=float,
                  default=None, 
                  help="Maximum total mass. OPTIONAL, if not provided the "
                       "max total mass is determined by the component masses."
                       " UNITS=Solar mass")
    massOpts.add_argument("--min-total-mass", action="store", type=float,
                  default=None, 
                  help="Minimum total mass. OPTIONAL, if not provided the "
                       "min total mass is determined by the component masses."
                       " UNITS=Solar mass")
    massOpts.add_argument("--max-chirp-mass", action="store", type=float,
                  default=None,
                  help="Maximum chirp mass. OPTIONAL, if not provided the "
                       "max chirp mass is determined by the component masses."
                       " UNITS=Solar mass")
    massOpts.add_argument("--min-chirp-mass", action="store", type=float,
                  default=None,
                  help="Minimum total mass. OPTIONAL, if not provided the "
                       "min chirp mass is determined by the component masses."
                       " UNITS=Solar mass")
    massOpts.add_argument("--max-eta", action="store", type=float,
                  default=0.25, 
                  help="Maximum symmetric mass ratio. OPTIONAL, no upper bound"
                       " on eta will be imposed if not provided. "
                       "UNITS=Solar mass.")
    massOpts.add_argument("--min-eta", action="store", type=float,
                  default=0., 
                  help="Minimum symmetric mass ratio. OPTIONAL, no lower bound"
                       " on eta will be imposed if not provided. "
                       "UNITS=Solar mass.")

    if nonSpin:
        parser.add_argument_group(massOpts)
        return

    massOpts.add_argument("--max-ns-spin-mag", action="store", type=float,
                  default=None,
                  help="Maximum neutron star spin magnitude.  Neutron stars "
                       "are defined as components lighter than 3 Msun. "
                       "REQUIRED if min-mass2 < 3 Msun")
    massOpts.add_argument("--max-bh-spin-mag", action="store", type=float,\
                  default=None,
                  help="Maximum black hole spin magnitude.  Black holes are "
                       "defined as components with mass >= 3 Msun. REQUIRED "
                       "if max-mass1 > 3 Msun")
    action = massOpts.add_mutually_exclusive_group(required=False)
    action.add_argument("--ns-bh-boundary-mass", action='store', type=float,
                  default=3,
                  help="Mass boundary between neutron stars and black holes. "
                       "Components below this mass are considered neutron "
                       "stars and are subject to the neutron star spin limits. "
                       "Components above are considered black holes and are "
                       "subject to the black hole spin limits. OPTIONAL, if "
                       "not set the default value of 3 is used.")
    action.add_argument("--nsbh-flag", action="store_true", default=False,
                  help="Set this flag if generating a bank that contains only "
                       "systems with 1 black hole and 1 neutron star. With "
                       "this flag set the heavier body will always be subject "
                       "to the black hole spin restriction and the lighter "
                       "to the neutron star spin restriction, regardless of "
                       "mass. OPTIONAL, if set this option will ignore any "
                       "value provided to --ns-bh-boundary-mass.")

def verify_mass_range_options(opts, parser, nonSpin=False):
    """
    Parses the metric calculation options given and verifies that they are
    correct.

    Parameters
    ----------
    opts : argparse.Values instance
        Result of parsing the input options with OptionParser
    parser : object
        The OptionParser instance.
    nonSpin : boolean, optional (default=False)
        If this is provided the spin-related options will not be checked.
    """
    if not opts.min_mass1:
        parser.error("Must supply --min-mass1")
    if not opts.min_mass2:
        parser.error("Must supply --min-mass2")
    if not opts.max_mass1:
        parser.error("Must supply --max-mass1")
    if not opts.max_mass2:
        parser.error("Must supply --max-mass2")
    # Mass1 must be the heavier!
    if opts.min_mass1 < opts.min_mass2:
        parser.error("min-mass1 cannot be less than min-mass2!")
    if opts.max_mass1 < opts.max_mass2:
        parser.error("max-mass1 cannot be less than max-mass2!")
    # If given are min/max total mass/chirp mass possible?
    if opts.min_total_mass:
        if opts.min_total_mass > opts.max_mass1 + opts.max_mass2:
            err_msg = "Supplied minimum total mass %f " %(opts.min_total_mass,)
            err_msg += "greater than the sum of the two max component masses "
            err_msg += " %f and %f." %(opts.max_mass1,opts.max_mass2)
    if opts.max_total_mass:
        if opts.max_total_mass < opts.min_mass1 + opts.min_mass2:
            err_msg = "Supplied maximum total mass %f " %(opts.max_total_mass,)
            err_msg += "smaller than the sum of the two min component masses "
            err_msg += " %f and %f." %(opts.min_mass1,opts.min_mass2)
            raise ValueError(err_msg)
    if opts.max_total_mass and opts.min_total_mass:
        if opts.max_total_mass < opts.min_total_mass:
            err_msg = "Min total mass must be larger than max total mass."
            raise ValueError(err_msg)

    # Assign min/max total mass from mass1, mass2 if not specified
    if (not opts.min_total_mass) or \
            ((opts.min_mass1 + opts.min_mass2) > opts.min_total_mass):
        opts.min_total_mass = opts.min_mass1 + opts.min_mass2
    if (not opts.max_total_mass) or \
            ((opts.max_mass1 + opts.max_mass2) < opts.max_total_mass):
        opts.max_total_mass = opts.max_mass1 + opts.max_mass2

    # It is vital that min and max total mass be set correctly.
    # This is becasue the heavily-used function get_random_mass will place
    # points first in total mass (to some power), and then in eta. If the total
    # mass limits are not well known ahead of time it will place unphysical
    # points and fail.
    # This test is a bit convoluted as we identify the maximum and minimum
    # possible total mass from chirp mass and/or eta restrictions.
    if opts.min_chirp_mass is not None:
        # Need to get the smallest possible min_tot_mass from this chirp mass
        # There are 4 possibilities for where the min_tot_mass is found on the
        # line of min_chirp_mass that interacts with the component mass limits.
        # Either it is found at max_m2, or at min_m1, or it starts on the equal
        # mass line within the parameter space, or it doesn't intersect
        # at all.
        # First let's get the masses at both of these possible points
        m1_at_max_m2 = pnutils.mchirp_mass1_to_mass2(opts.min_chirp_mass,
                                                     opts.max_mass2)
        if m1_at_max_m2 < opts.max_mass2:
            # Unphysical, remove
            m1_at_max_m2 = -1
        m2_at_min_m1 = pnutils.mchirp_mass1_to_mass2(opts.min_chirp_mass,
                                                      opts.min_mass1)
        if m2_at_min_m1 > opts.min_mass1:
            # Unphysical, remove
            m2_at_min_m1 = -1
        # Get the values on the equal mass line
        m1_at_equal_mass, m2_at_equal_mass = pnutils.mchirp_eta_to_mass1_mass2(\
                                                     opts.min_chirp_mass, 0.25)

        # Are any of these possible?
        if m1_at_max_m2 <= opts.max_mass1 and m1_at_max_m2 >= opts.min_mass1:
            min_tot_mass = opts.max_mass2 + m1_at_max_m2
        elif m2_at_min_m1 <= opts.max_mass2 and m2_at_min_m1 >= opts.min_mass2:
            min_tot_mass = opts.min_mass1 + m2_at_min_m1
        elif m1_at_equal_mass <= opts.max_mass1 and \
                 m1_at_equal_mass >= opts.min_mass1 and\
                 m2_at_equal_mass <= opts.max_mass2 and\
                 m2_at_equal_mass >= opts.min_mass2:
            min_tot_mass = m1_at_equal_mass + m2_at_equal_mass
        # So either the restriction is low enough to be redundant, or is
        # removing all the paramter space
        elif m2_at_min_m1 < opts.min_mass_2:
            # This is the redundant case, ignore
            min_tot_mass = opts.min_total_mass
        else:
            # And this is the bad case
            err_msg = "The minimum chirp mass provided is not possible given "
            err_msg += "restrictions on component masses."
            raise ValueError(err_msg)
        # Is there also an eta restriction?
        if opts.max_eta:
            # Get the value of m1,m2 at max_eta, min_chirp_mass
            max_eta_m1, max_eta_m2 = pnutils.mchirp_eta_to_mass1_mass2(
                                         opts.min_chirp_mass, opts.max_eta)
            max_eta_min_tot_mass = max_eta_m1 + max_eta_m2
            if max_eta_min_tot_mass > min_tot_mass:
                # Okay, eta does restrict this further. Still physical?
                min_tot_mass = max_eta_min_tot_mass
                if max_eta_m1 > opts.max_mass1:
                    err_msg = "The combination of component mass, chirp "
                    err_msg += "mass, eta and (possibly) total mass limits "
                    err_msg += "have precluded all systems."
                    raise ValueError(err_msg)
        # Update min_tot_mass if needed
        if min_tot_mass > opts.min_total_mass:
            opts.min_total_mass = float(min_tot_mass)
    # Need to check max_eta alone for minimum mass
    if opts.max_eta:
        # Similar to above
        # Need to get the smallest possible min_tot_mass from this eta.
        # There are 3 possibilities for where the min_tot_mass is found on the
        # line of max_eta that interacts with the component mass limits.
        # Either it is found at min_m2, or at min_m1, or it doesn't intersect
        # at all (ie. this chirp mass is not possible).
        # First let's get the masses at both of these possible points
        m1_at_min_m2 = pnutils.eta_mass1_to_mass2(opts.max_eta, opts.min_mass2,
                                                      return_mass_heavier=True)
        m2_at_min_m1 = pnutils.eta_mass1_to_mass2(opts.max_eta, opts.min_mass1,
                                                     return_mass_heavier=False)
        # Are either of these possible?
        if m1_at_min_m2 <= opts.max_mass1 and m1_at_min_m2 >= opts.min_mass1:
            min_tot_mass = opts.min_mass2 + m1_at_min_m2
        elif m2_at_min_m1 <= opts.max_mass2 and m2_at_min_m1 >= opts.min_mass2:
            min_tot_mass = opts.min_mass1 + m2_at_min_m1
        # So either the restriction is low enough to be redundant, or is
        # removing all the paramter space
        elif m2_at_min_m1 > opts.max_mass1:
            # This is the redundant case, ignore
            min_tot_mass = opts.min_total_mass
        else:
            # And this is the bad case
            err_msg = "The maximum eta provided is not possible given "
            err_msg += "restrictions on component masses."
            raise ValueError(err_msg)
        # Update min_tot_mass if needed
        if min_tot_mass > opts.min_total_mass:
            opts.min_total_mass = float(min_tot_mass)

    # Then need to do max_chirp_mass and min_eta
    if opts.max_chirp_mass is not None:
        # Need to get the largest possible maxn_tot_mass from this chirp mass
        # There are 3 possibilities for where the max_tot_mass is found on the
        # line of max_chirp_mass that interacts with the component mass limits.
        # Either it is found at min_m2, or at max_m1, or it doesn't intersect
        # at all.
        # First let's get the masses at both of these possible points
        m1_at_min_m2 = pnutils.mchirp_mass1_to_mass2(opts.max_chirp_mass,
                                                     opts.min_mass2)
        m2_at_max_m1 = pnutils.mchirp_mass1_to_mass2(opts.max_chirp_mass,
                                                      opts.max_mass1)
        # Are either of these possible?
        if m1_at_min_m2 <= opts.max_mass1 and m1_at_min_m2 >= opts.min_mass1:
            max_tot_mass = opts.min_mass2 + m1_at_min_m2
        elif m2_at_max_m1 <= opts.max_mass2 and m2_at_max_m1 >= opts.min_mass2:
            max_tot_mass = opts.max_mass1 + m2_at_max_m1
        # So either the restriction is low enough to be redundant, or is
        # removing all the paramter space
        elif m2_at_max_m1 > opts.max_mass2:
            # This is the redundant case, ignore
            max_tot_mass = opts.max_total_mass
        else:
            # And this is the bad case
            err_msg = "The maximum chirp mass provided is not possible given "
            err_msg += "restrictions on component masses."
            raise ValueError(err_msg)
        # Is there also an eta restriction?
        if opts.min_eta:
            # Get the value of m1,m2 at max_eta, min_chirp_mass
            min_eta_m1, min_eta_m2 = pnutils.mchirp_eta_to_mass1_mass2(
                                         opts.max_chirp_mass, opts.min_eta)
            min_eta_max_tot_mass = min_eta_m1 + min_eta_m2
            if min_eta_max_tot_mass < max_tot_mass:
                # Okay, eta does restrict this further. Still physical?
                max_tot_mass = min_eta_max_tot_mass
                if min_eta_m1 < opts.min_mass1:
                    err_msg = "The combination of component mass, chirp "
                    err_msg += "mass, eta and (possibly) total mass limits "
                    err_msg += "have precluded all systems."
                    raise ValueError(err_msg)
        # Update min_tot_mass if needed
        if max_tot_mass < opts.max_total_mass:
            opts.max_total_mass = float(max_tot_mass)
    # Need to check min_eta alone for maximum total mass
    if opts.min_eta:
        # Similar to above
        # Need to get the largest possible max_tot_mass from this eta.
        # There are 3 possibilities for where the max_tot_mass is found on the
        # line of min_eta that interacts with the component mass limits.
        # Either it is found at max_m2, or at max_m1, or it doesn't intersect
        # at all (ie. this eta is not possible).
        # First let's get the masses at both of these possible points
        m1_at_max_m2 = pnutils.eta_mass1_to_mass2(opts.min_eta, opts.max_mass2,
                                                      return_mass_heavier=True)
        m2_at_max_m1 = pnutils.eta_mass1_to_mass2(opts.min_eta, opts.max_mass1,
                                                     return_mass_heavier=False)
        # Are either of these possible?
        if m1_at_max_m2 <= opts.max_mass1 and m1_at_max_m2 >= opts.min_mass1:
            max_tot_mass = opts.max_mass2 + m1_at_max_m2
        elif m2_at_max_m1 <= opts.max_mass2 and m2_at_max_m1 >= opts.min_mass2:
            max_tot_mass = opts.max_mass1 + m2_at_max_m1
        # So either the restriction is low enough to be redundant, or is
        # removing all the paramter space
        elif m2_at_max_m1 < opts.min_mass1:
            # This is the redundant case, ignore
            max_tot_mass = opts.max_total_mass
        else:
            # And this is the bad case
            err_msg = "The minimum eta provided is not possible given "
            err_msg += "restrictions on component masses."
            raise ValueError(err_msg)
        # Update min_tot_mass if needed
        if max_tot_mass < opts.max_total_mass:
            opts.max_total_mass = float(max_tot_mass)

    if opts.max_eta and opts.min_eta:
        if opts.max_eta < opts.min_eta:
            parser.error("--max-eta must be larger than --min-eta.")
    if nonSpin:
        return
    if opts.max_ns_spin_mag is None:
        # Can ignore this if no NSs will be generated
        if opts.min_mass2 < 3:
            parser.error("Must supply --max-ns-spin-mag")
        else:
            opts.max_ns_spin_mag = opts.max_bh_spin_mag
    if opts.max_bh_spin_mag is None:
        # Can ignore this if no BHs will be generated
        if opts.max_mass1 > 3:
            parser.error("Must supply --max-bh-spin-mag")
        else:
            opts.max_bh_spin_mag = opts.max_ns_spin_mag

class massRangeParameters(object):
    """
    This class holds all of the options that are parsed in the function
    insert_mass_range_option_group
    and all products produced using these options. It can also be initialized
    from the __init__ function providing directly the options normally
    provided on the command line
    """
    def __init__(self, minMass1, maxMass1, minMass2, maxMass2,
                 maxNSSpinMag=0, maxBHSpinMag=0, maxTotMass=None,
                 minTotMass=None, maxEta=None, minEta=0, 
                 max_chirp_mass=None, min_chirp_mass=None, 
                 ns_bh_boundary_mass=3.0, nsbhFlag=False):
        """
        Initialize an instance of the massRangeParameters by providing all
        options directly. See the help message associated with any code
        that uses the metric options for more details of how to set each of
        these. For e.g. pycbc_aligned_stoch_bank --help
        """
        self.minMass1=minMass1
        self.maxMass1=maxMass1
        self.minMass2=minMass2
        self.maxMass2=maxMass2
        self.maxNSSpinMag=maxNSSpinMag
        self.maxBHSpinMag=maxBHSpinMag
        self.minTotMass = minMass1 + minMass2
        if minTotMass and (minTotMass > self.minTotMass):
            self.minTotMass = minTotMass
        self.maxTotMass = maxMass1 + maxMass2
        if maxTotMass and (maxTotMass < self.maxTotMass):
            self.maxTotMass = maxTotMass
        self.maxTotMass=maxTotMass
        self.minTotMass=minTotMass
        if maxEta:
            self.maxEta=maxEta
        else:
            self.maxEta=0.25
        self.max_chirp_mass = max_chirp_mass
        self.min_chirp_mass = min_chirp_mass
        self.minEta=minEta
        self.ns_bh_boundary_mass = ns_bh_boundary_mass
        self.nsbhFlag=nsbhFlag

        # FIXME: This may be inaccurate if Eta limits are given
        # This will not cause any problems, but maybe could be fixed.
        self.minCompMass = self.minMass2
        self.maxCompMass = self.maxMass1

        # WARNING: We expect mass1 > mass2 ALWAYS
        # Check input:
        if (minMass2 > minMass1) or (maxMass2 > maxMass1):
            errMsg = "Mass1 must be larger than mass2. Check input options."
            raise ValueError(errMsg)

        if (minMass2 > maxMass2) or (minMass1 > maxMass1):
            errMsg = "Minimum masses cannot be larger than maximum masses."
            errMsg += "Check input options."
            raise ValueError(errMsg)


    @classmethod
    def from_argparse(cls, opts, nonSpin=False):
        """
        Initialize an instance of the massRangeParameters class from an
        argparse.OptionParser instance. This assumes that
        insert_mass_range_option_group
        and
        verify_mass_range_options
        have already been called before initializing the class.
        """
        if nonSpin:
            return cls(opts.min_mass1, opts.max_mass1, opts.min_mass2,\
                       opts.max_mass2, maxTotMass=opts.max_total_mass,\
                       minTotMass=opts.min_total_mass, maxEta=opts.max_eta,\
                       minEta=opts.min_eta, max_chirp_mass=opts.max_chirp_mass,\
                       min_chirp_mass=opts.min_chirp_mass)
        else:
            return cls(opts.min_mass1, opts.max_mass1, opts.min_mass2,\
                       opts.max_mass2, maxTotMass=opts.max_total_mass,\
                       minTotMass=opts.min_total_mass, maxEta=opts.max_eta,\
                       minEta=opts.min_eta, maxNSSpinMag=opts.max_ns_spin_mag,\
                       maxBHSpinMag=opts.max_bh_spin_mag, \
                       nsbhFlag=opts.nsbh_flag,
                       max_chirp_mass=opts.max_chirp_mass,
                       min_chirp_mass=opts.min_chirp_mass,
                       ns_bh_boundary_mass=opts.ns_bh_boundary_mass)

    def is_unphysical(self, mass1, mass2, spin1z, spin2z):
        """
        Test if a given location in mass1, mass2, spin1z, spin2z is within the
        range of parameters allowed by the massParams object.
        """
        # Mass1 test
        if mass1 < self.minMass1:
            return 1
        if mass1 > self.maxMass1:
            return 1
        # Mass2 test
        if mass2 < self.minMass2:
            return 1
        if mass2 > self.maxMass2:
            return 1
        # Spin1 test
        if self.nsbhFlag:
            if (abs(spin1z) > self.maxBHSpinMag):
                return 1
        else:
            spin1zM = abs(spin1z)
            if not( (mass1 > self.ns_bh_boundary_mass \
                     and spin1zM <= self.maxBHSpinMag) \
                 or (mass1 < self.ns_bh_boundary_mass \
                     and spin1zM <= self.maxNSSpinMag)):
                return 1
        # Spin2 test
        if self.nsbhFlag:
            if (abs(spin2z) > self.maxNSSpinMag):
                return 1
        else:
            spin2zM = abs(spin2z)
            if not( (mass2 > self.ns_bh_boundary_mass \
                     and spin2zM <= self.maxBHSpinMag) \
                 or (mass2 < self.ns_bh_boundary_mass and \
                     spin2zM <= self.maxNSSpinMag)):
                return 1
        # Total mass test
        mTot = mass1 + mass2
        if mTot > self.maxTotMass:
            return 1
        if mTot < self.minTotMass:
            return 1

        # Eta test
        eta = mass1 * mass2 / (mTot * mTot)
        if eta > self.maxEta:
            return 1
        if eta < self.minEta:
            return 1

        # Chirp mass test
        chirp_mass = mTot * eta**(3./5.)
        if self.min_chirp_mass is not None:
            if chirp_mass < min_chirp_mass:
                return 1
        if self.max_chirp_mass is not None:
            if chirp_mass > max_chirp_mass:
                return

        return 0

class ethincaParameters:
    """
    This class holds all of the options that are parsed in the function
    insert_ethinca_option_group
    and all products produced using these options. It can also be initialized
    from the __init__ function, providing directly the options normally
    provided on the command line
    """
    def __init__(self, pnOrder, cutoff, freqStep, fLow=None, doEthinca=False):
        """
        Initialize an instance of ethincaParameters by providing all
        options directly.  See the insert_ethinca_option_group() function
        for explanation or e.g. run pycbc_geom_nonspinbank --help
        """
        self.doEthinca=doEthinca
        self.pnOrder=pnOrder
        self.cutoff=cutoff
        self.freqStep=freqStep
        # independent fLow for ethinca metric is currently not used
        self.fLow=fLow
        # check that ethinca options make sense
        if doEthinca and not (
                cutoff in pnutils.get_frequency_cutoffs().keys()):
            raise ValueError("Need a valid cutoff formula to calculate "
                             "ethinca! Possible values are "+
                             str(pnutils.get_frequency_cutoffs().keys()))
        if doEthinca and not freqStep:
            raise ValueError("Need to specify a cutoff frequency step to "
                             "calculate ethinca! (ethincaFreqStep)")

    @classmethod
    def from_argparse(cls, opts):
        """
        Initialize an instance of the ethincaParameters class from an
        argparse.OptionParser instance. This assumes that
        insert_ethinca_option_group
        and
        verify_ethinca_metric_options
        have already been called before initializing the class.
        """
        return cls(opts.ethinca_pn_order, opts.ethinca_cutoff,
            opts.ethinca_frequency_step, fLow=None,
            doEthinca=opts.calculate_ethinca_metric)

def insert_ethinca_metric_options(parser):
    """
    Adds the options used to calculate the ethinca metric, if required.
 
    Parameters
    -----------
    parser : object
        OptionParser instance.
    """
    ethincaGroup = parser.add_argument_group("Ethinca metric options",
                    "Options used in the calculation of Gamma metric "
                    "components for the ethinca coincidence test.")
    ethincaGroup.add_argument("--calculate-ethinca-metric",
                    action="store_true", default=False, 
                    help="If given, the ethinca metric will be calculated "
                    "and stored in the Gamma entries of the sngl_inspiral "
                    "table.  OPTIONAL")
    ethincaGroup.add_argument("--ethinca-pn-order",
                    default=None, choices=get_ethinca_orders(), 
                    help="Specify a PN order to be used in calculating the "
                    "ethinca metric.  OPTIONAL: if not specified, the same "
                    "order will be used as for the bank metric.")
    ethincaGroup.add_argument("--ethinca-cutoff",
                    default=None, 
                    choices=pnutils.get_frequency_cutoffs().keys(),
                    help="Specify an upper frequency cutoff formula for the "
                    "ethinca metric calculation.  REQUIRED if the "
                    "calculate-ethinca-metric option is given.")
    ethincaGroup.add_argument("--ethinca-frequency-step", action="store",
                    type=float, default=10.,
                    help="Control the precision with which the upper "
                    "frequency cutoff is specified.  For speed, the metric "
                    "is calculated only for discrete f_max values with a "
                    "spacing given by this option.  Each template is then "
                    "assigned the result for the f_max closest to its "
                    "analytical cutoff formula.  OPTIONAL. UNITS=Hz")

def verify_ethinca_metric_options(opts, parser):
    """
    Checks that the necessary options are given for the ethinca metric
    calculation.

    Parameters
    ----------
    opts : argparse.Values instance
        Result of parsing the input options with OptionParser
    parser : object
        The OptionParser instance.
    """
    if opts.calculate_ethinca_metric and not (opts.ethinca_cutoff in
              pnutils.get_frequency_cutoffs().keys()):
        parser.error("Need a valid cutoff formula to calculate ethinca! "
                     "Possible values are "
                     +str(pnutils.get_frequency_cutoffs().keys()))
    if opts.calculate_ethinca_metric and not opts.ethinca_frequency_step:
        parser.error("Need to specify a cutoff frequency step to calculate "
                     "ethinca!")
    if not opts.calculate_ethinca_metric and opts.ethinca_cutoff:
        parser.error("Can't specify an ethinca cutoff formula if not "
                     "calculating ethinca metric!")
    if not opts.calculate_ethinca_metric and opts.ethinca_pn_order:
        parser.error("Can't specify an ethinca PN order if not "
                     "calculating ethinca metric!")

def check_ethinca_against_bank_params(ethincaParams, metricParams):
    """
    Cross-check the ethinca and bank layout metric calculation parameters
    and set the ethinca metric PN order equal to the bank PN order if not
    previously set.

    Parameters
    ----------
    ethincaParams: instance of ethincaParameters
    metricParams: instance of metricParameters
    """
    if ethincaParams.doEthinca is True:
        if metricParams.f0 != metricParams.fLow:
            raise ValueError("If calculating ethinca metric, f0 and f-low "
                             "must be equal!")
        if ethincaParams.fLow is not None and (
                ethincaParams.fLow != metricParams.fLow):
            raise ValueError("Ethinca metric calculation does not currently "
                             "support a f-low value different from the bank "
                             "metric!")
        if ethincaParams.pnOrder == None:
            ethincaParams.pnOrder = metricParams.pnOrder
    else: pass

def check_ethinca_against_bank_opts(opts, parser):
    """
    Cross-check the ethinca and bank layout metric options.
    The Params-level function 'check_ethinca_against_bank_params' is 
    preferred to this function since it operates directly on the Params
    objects which are passed to the ethinca metric calculation, and can 
    change their attributes if desired.

    Parameters
    ----------
    opts : argparse.Values instance
        Result of parsing the input options with OptionParser
    parser : object
        The OptionParser instance.
    """
    if ethincaParams.doEthinca is True:
        if opts.f0 != opts.f_low:
            parser.error("If calculating ethinca metric, f0 and f-low "
                         "must be equal!")
        if opts.ethinca_f_low is not None and (
                opts.ethinca_f_low != opts.f_low):
            parser.error("Ethinca metric calculation does not currently "
                         "support a f-low value different from the bank "
                         "metric!")
    else: pass

