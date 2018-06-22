classdef SCENFileReader < object_oriented_simcap.Readers.MAGICCDataFileReader
    methods (Access = protected)
        function set_header_rows_tmp(self)
            header_rows = {'Region';'Variable';'Unit'};
            numeric_data_line_idxs = find(...
                self.return_numerical_data_lines_idxs...
            );
            for i=1:length(numeric_data_line_idxs)
                line_number = numeric_data_line_idxs(i);
                if startsWith(self.file_lines{line_number-1},'Yrs')
                    unit_line = strsplit(self.file_lines{line_number-1});
                    units_only = unit_line(2:end);
                    variable_line = strsplit(self.file_lines{line_number-2});
                    variable_only = variable_line(2:end);
                    regions = repmat(...
                        self.file_lines(line_number-3),...
                        1,length(variable_only)...
                    );
                    header_rows = [...
                        header_rows...
                        [regions;variable_only;units_only]...
                    ];
                end
            end
            self.header_rows_tmp = header_rows;
        end
        function numeric_rows = return_datablock_numeric_rows(self)
            numeric_rows = self.return_reshaped_SCEN_numeric_rows(...
                return_datablock_numeric_rows@object_oriented_simcap.Readers.MAGICCDataFileReader(self)...
            );
        end
        function numeric_rows_out = return_reshaped_SCEN_numeric_rows(self,numeric_rows_in)
            years = unique(numeric_rows_in(:,1));
            number_of_years = length(years);
            number_of_regions = size(numeric_rows_in,1)/number_of_years;
            numeric_rows_out = years;
            for i=1:number_of_regions
                start_row = number_of_years*(i-1) + 1; 
                end_row = number_of_years*i;
                numeric_rows_out = [...
                    numeric_rows_out...
                    numeric_rows_in(start_row:end_row,2:end)...
                ];
            end
        end
        function numerical_data_lines_idxs = return_numerical_data_lines_idxs(self)
            numerical_data_lines_idxs = return_numerical_data_lines_idxs@object_oriented_simcap.Readers.MAGICCDataFileReader(self);
            numerical_data_lines_idxs(1:2) = false;
        end
        function read_notes(self)
            self.data.Notes = self.file_lines(3:4); 
        end
    end
end