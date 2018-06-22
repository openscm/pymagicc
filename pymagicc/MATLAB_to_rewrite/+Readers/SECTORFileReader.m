classdef SECTORFileReader < object_oriented_simcap.Readers.MAGICCDataFileReader
    methods (Access = protected)
        function make_Region_header_row_in_header_rows_tmp(self)
            Replace_cell_idx = strcmp(self.header_rows_tmp,'COLCODE');
            self.header_rows_tmp(Replace_cell_idx) = {'Region'};
        end
        function make_Variable_header_row_in_header_rows_tmp(self)
            GAS_cell_idx = strcmp(self.header_rows_tmp,'GAS');
            self.header_rows_tmp(GAS_cell_idx) = {'Variable'};
        end
    end
end