classdef MAGICCDataFileReader < handle
    properties
        data
    end
    
    properties (Access = protected)
        fid
        file_lines
        
        datablock_cell
        header_rows_tmp
        
        DataTableManipulator = object_oriented_simcap.DataTableManipulators.MAGICCDataTableManipulator
        
        fortran_namelist_value_regexp = '(\d+|"\S+")'
        
        data_notes
        data_table_notes_cell
        DataWriter = object_oriented_simcap.Writers.MAGICCDataFileWriter
    end
    
    methods
        function self = MAGICCDataFileReader
            self.data = object_oriented_simcap.MAGICCData;
        end
        
        function read_MAGICC_data_file(self,data_file)
            self.data.full_path_source_file = data_file;
            self.read_file_to_file_lines(data_file)
            self.read_descriptor_fields
            self.read_in_data_table
            self.read_notes
        end
    end
    
    methods (Access = protected)
        function read_file_to_file_lines(self,file_full_path)
            split_lines = strsplit(fileread(file_full_path),newline);
            stripped_lines = strip(split_lines);
            self.file_lines = object_oriented_simcap.Utils.convert_to_column_vector(stripped_lines);
        end
        function read_descriptor_fields(self)
            for i=1:length(self.data.descriptor_strings)
                relevant_line_idxs = startsWith(...
                    self.file_lines,...
                    self.data.descriptor_strings{i},...
                    'IgnoreCase',true...
                );
                if ~any(relevant_line_idxs);continue;end
                relevant_lines = unique(self.file_lines(relevant_line_idxs));
                value_only = cellfun(...
                    @(x) char(strip(extractAfter(x,':'))),...
                    relevant_lines,...
                    'UniformOutput',false...
                );
                self.data.(self.data.descriptor_fields{i}) = strjoin(value_only);
            end 
        end
        function read_in_data_table(self)
            self.data.data_table = self.DataTableManipulator.convert_wide_data_to_long_and_return(...
                self.return_wide_data_cell...
            );
        end
        
        function wide_data_cell = return_wide_data_cell(self)
            wide_data_cell = [...
                self.return_datablock_header_rows;...
                num2cell(self.return_datablock_numeric_rows)...
            ];
        end
        function header_rows = return_datablock_header_rows(self)
            self.set_header_rows_tmp
            self.tidy_header_rows_tmp
            header_rows = self.header_rows_tmp;
        end
        function set_header_rows_tmp(self)
            header_rows_split = cellfun(...
                @strsplit,...
                self.file_lines(self.return_header_data_lines_idxs),...
                'UniformOutput',false...
            );
            self.header_rows_tmp = vertcat(header_rows_split{:});
        end
        function header_data_lines_idxs = return_header_data_lines_idxs(self)
            header_data_lines_idxs = false(length(self.file_lines),1);
            first_data_line = find(self.return_numerical_data_lines_idxs,1);
            potential_header_line_idx = first_data_line - 1;
            while is_header_line(self.file_lines{potential_header_line_idx})
                header_data_lines_idxs(potential_header_line_idx) = true;
                potential_header_line_idx = potential_header_line_idx - 1;
            end
            function val = is_header_line(line_to_test)
                val = ~isempty(strip(line_to_test))...
                      & ~strcmp(strip(line_to_test),'/');
            end
        end
        
        function numeric_rows = return_datablock_numeric_rows(self)
            numeric_rows = str2double(split(...
                self.file_lines(self.return_numerical_data_lines_idxs)...
            ));
        end
        function numerical_data_lines_idxs = return_numerical_data_lines_idxs(self)
            digits = {'1' '2' '3' '4' '5' '6' '7' '8' '9' '0'};
            numerical_data_lines_idxs = ~self.return_notes_line_idxs...
                                        & startsWith(self.file_lines,digits);
        end
        
        function tidy_header_rows_tmp(self)
            for final_table_column = self.data.data_table.Properties.VariableNames
                self.tidy_header_row(final_table_column{1})
            end
        end
        function tidy_header_row(self,header_row)
            if strcmp(header_row,'Region')
                self.tidy_Region_metadata
            elseif strcmp(header_row,'Variable')
                self.tidy_Variable_metadata
            elseif strcmp(header_row,'Unit')
                self.tidy_Unit_metadata
            elseif strcmp(header_row,'TODO')
                self.tidy_TODO_metadata
            elseif ismember(header_row,{'Notes' 'Year' 'Value'})
                
            else
                error_msg = [...
                    'I don''t know how to produce a tidy ' header_row ...
                    ' row to read into the MAGICCData data_table'...
                ];
                error(...
                    'MAGICCDataReaderError:unrecognised_column',...
                    error_msg...
                )
            end
        end
        
        function tidy_Region_metadata(self)
            region_cell_idx = strcmpi(self.header_rows_tmp,'REGION');
            if any(region_cell_idx(:)) 
                self.header_rows_tmp(region_cell_idx) = {'Region'};
            else
                self.make_Region_header_row_in_header_rows_tmp
            end
        end
        function make_Region_header_row_in_header_rows_tmp(self)
            self.header_rows_tmp(end,1) = {'Region'};
        end
        function tidy_Variable_metadata(self)
            variable_cell_idx = strcmpi(self.header_rows_tmp,'Variable');
            if any(variable_cell_idx(:))
                self.header_rows_tmp(variable_cell_idx) = {'Variable'};
            else
                self.make_Variable_header_row_in_header_rows_tmp
            end 
        end
        function make_Variable_header_row_in_header_rows_tmp(self) 
        end
        function tidy_Unit_metadata(self)
            unit_cell_idx = strcmpi(self.header_rows_tmp,'Unit')...
                            | strcmpi(self.header_rows_tmp,'Units');
            if any(unit_cell_idx(:))
                self.header_rows_tmp(unit_cell_idx) = {'Unit'};
            else
                self.make_Unit_header_row_in_header_rows_tmp
            end
        end
        function make_Unit_header_row_in_header_rows_tmp(self)
            repeated_unit_cell = repmat(...
                self.read_THISFILE_UNITS,...
                1,size(self.header_rows_tmp,2)-1 ...
            );
            unit_row = ['Unit' repeated_unit_cell];
            self.header_rows_tmp = [unit_row;self.header_rows_tmp];
        end
        function tidy_TODO_metadata(self)
            TODO_cell_idx = strcmpi(self.header_rows_tmp,'TODO');
            if any(TODO_cell_idx(:))
                self.header_rows_tmp(TODO_cell_idx) = {'TODO'};
            else
                self.make_TODO_header_row_in_header_rows_tmp
            end
        end
        function make_TODO_header_row_in_header_rows_tmp(self)
            repeated_TODO_cell = repmat(...
                {'SET'},...
                1,size(self.header_rows_tmp,2)-1 ...
            );
            TODO_row = ['TODO' repeated_TODO_cell];
            self.header_rows_tmp = [TODO_row;self.header_rows_tmp];
        end
        
        function unit = read_THISFILE_UNITS(self)
            units_line_idx = startsWith(self.file_lines,'THISFILE_UNITS');
            unit = {self.return_value_from_fortran_namelist_line(...
                self.file_lines{units_line_idx}...
            )};
                
        end
        
        function value = return_value_from_fortran_namelist_line(self,namelist_line)
            value_cell = regexp(...
                namelist_line,...
                self.fortran_namelist_value_regexp,...
                'match'...
            );
            if is_string_value(value_cell{1})
                value = strip(value_cell{1},'"');
%             else
%                 value = str2double(value_cell{1});
            end
            
            function return_var = is_string_value(value_string)
                return_var = contains(value_string,'"') ;
            end
        end
        
        function read_notes(self)
            notes_lines = self.file_lines(self.return_notes_line_idxs);
            if isempty(notes_lines)
                return;end
            end_general_notes_idx = self.return_end_general_notes_idx_in_notes_lines(notes_lines);
            self.data.Notes = notes_lines(1:end_general_notes_idx);
            self.data_notes = notes_lines(end_general_notes_idx+2:end);
            self.read_in_data_notes
        end
        function notes_line_idxs = return_notes_line_idxs(self)
            notes_line_idxs = false(length(self.file_lines),1);
            start_notes_idx = self.return_start_notes_idx;
            if start_notes_idx ~= 0
                end_notes_idx = self.return_end_notes_idx;
                notes_line_idxs(start_notes_idx:end_notes_idx) = true;
            end
        end
        function start_idx = return_start_notes_idx(self)
            header_line_idxs = find(...
                strcmp(self.file_lines,self.DataWriter.notes_start_line)...
            );
            if isempty(header_line_idxs)
                start_idx = 0;
            else
                i = 1;
                next_line = self.file_lines{header_line_idxs(i)+1};
                while ~strcmp(next_line,self.DataWriter.notes_start_line_underline)
                    i = i + 1;
                    next_line = self.file_lines{header_line_idxs(i)+1};
                end
                start_idx = header_line_idxs(i) + 2;
            end
        end
        function end_notes_idx = return_end_notes_idx(self)
            end_notes_idx = -1 + find(...
                strcmp(self.DataWriter.notes_end_line,self.file_lines)...
            );
        end
        function end_general_notes_idx = return_end_general_notes_idx_in_notes_lines(self,notes_lines)
            end_general_notes_idx = -1 + find(strcmp(...
                notes_lines,...
                self.DataWriter.general_data_notes_split_line...
            ));
        end
        
        function read_in_data_notes(self)
            line_no = 1;
            self.data_table_notes_cell = self.data.data_table.Notes;
            while line_no <= length(self.data_notes)
                if self.line_number_of_data_notes_is_year_indicator(line_no)
                    line_no = self.add_year_notes_strt_at_line_no_in_notes_rtrn_nxt_line_no(...
                        line_no...
                    );
                elseif self.line_number_of_data_notes_is_region_indicator(line_no)
                    line_no = self.add_region_notes_strt_at_line_no_in_notes_rtrn_nxt_line_no(...
                        line_no...
                    );
                elseif self.line_number_of_data_notes_is_variable_indicator(line_no)
                    line_no = self.add_variable_notes_strt_at_line_no_in_notes_rtrn_nxt_line_no(...
                        line_no...
                    );
                elseif isempty(self.data_notes{line_no})
                    line_no = line_no + 1;
                else
                    self.add_note_to_data_table_notes_cell(...
                        self.data_notes{line_no},...
                        true(length(self.data.data_table.Notes),1)...
                    )
                    line_no = line_no + 1;
                end
            end
            self.data.data_table.Notes = self.data_table_notes_cell;
        end
        
        function next_line_no = add_variable_notes_strt_at_line_no_in_notes_rtrn_nxt_line_no(self,start_line_no)
            variable_rows = strcmp(...
                self.data.data_table.Variable,...
                self.data_notes{start_line_no}...
            );
            line_no = start_line_no + 2;
            while line_no <= length(self.data_notes)...
                  && ~self.line_number_of_data_notes_is_variable_indicator(line_no)
                if isempty(self.data_notes{line_no})
                    line_no = line_no + 1;continue;end
                    % pushed continue up a line to maintain code coverage
                % pushed end up two lines to maintain code coverage
                
                if self.line_number_of_data_notes_is_year_indicator(line_no)
                    year_rows = self.data.data_table.Year...
                                == str2double(self.data_notes{line_no});
                    start_notes_line_no = line_no+2;
                    line_no = self.add_to_rows_start_at_line_no_in_data_notes_return_next_line_no(...
                        variable_rows & year_rows,...
                        start_notes_line_no...
                    );
                elseif self.line_number_of_data_notes_is_region_indicator(line_no)
                    region_rows = strcmp(...
                        self.data.data_table.Region,...
                        self.data_notes{line_no}...
                    );
                    start_notes_line_no = line_no+2;
                    line_no = self.add_to_rows_start_at_line_no_in_data_notes_return_next_line_no(...
                        variable_rows & region_rows,...
                        start_notes_line_no...
                    );
                    while line_no <= length(self.data_notes)...
                          && self.line_number_of_data_notes_is_year_indicator(line_no)...
                        years_rows = self.data.data_table.Year...
                                     == str2double(self.data_notes{line_no});
                        start_notes_line_no = line_no+2;
                        line_no = self.add_to_rows_start_at_line_no_in_data_notes_return_next_line_no(...
                            variable_rows & region_rows & years_rows,...
                            start_notes_line_no...
                        );
                    end
                else
                    start_notes_line_no = line_no;
                    line_no = self.add_to_rows_start_at_line_no_in_data_notes_return_next_line_no(...
                        variable_rows,...
                        start_notes_line_no...
                    );
                end
            end
            next_line_no = line_no;
        end
        function next_line_no = add_region_notes_strt_at_line_no_in_notes_rtrn_nxt_line_no(self,start_line_no)
            region_rows = strcmp(...
                self.data.data_table.Region,...
                self.data_notes{start_line_no}...
            );
            line_no = start_line_no + 2;
            while line_no <= length(self.data_notes)...
                  && ~self.line_number_of_data_notes_is_region_indicator(line_no)...
                  && ~self.line_number_of_data_notes_is_variable_indicator(line_no)
                if isempty(self.data_notes{line_no})
                    line_no = line_no + 1;continue;end
                    % pushed continue up a line to maintain code coverage
                % pushed end up two lines to maintain code coverage
                if self.line_number_of_data_notes_is_year_indicator(line_no)
                    year_rows = self.data.data_table.Year...
                                == str2double(self.data_notes{line_no});
                    start_notes_line_no = line_no+2;
                    line_no = self.add_to_rows_start_at_line_no_in_data_notes_return_next_line_no(...
                        region_rows & year_rows,...
                        start_notes_line_no...
                    );
                else
                    start_notes_line_no = line_no;
                    line_no = self.add_to_rows_start_at_line_no_in_data_notes_return_next_line_no(...
                        region_rows,...
                        start_notes_line_no...
                    );
                end
            end
            next_line_no = line_no;
        end
        function next_line_no = add_year_notes_strt_at_line_no_in_notes_rtrn_nxt_line_no(self,start_line_no)
            years_rows = self.data.data_table.Year...
                         == str2double(self.data_notes{start_line_no});
            start_notes_line_no = start_line_no+2;
            next_line_no = self.add_to_rows_start_at_line_no_in_data_notes_return_next_line_no(...
                years_rows,...
                start_notes_line_no...
            );
        end
        function next_line_no = add_to_rows_start_at_line_no_in_data_notes_return_next_line_no(self,rows2addto,start_line_no)
            line_no = start_line_no;
            while line_no <= length(self.data_notes)...
                  && ~self.line_number_of_data_notes_is_any_indicator(line_no)
                if ~isempty(self.data_notes{line_no})
                    self.add_note_to_data_table_notes_cell(...
                        self.data_notes{line_no},...
                        rows2addto...
                    )
                end
                line_no = line_no + 1;
            end
            next_line_no = line_no;
        end
        
        function return_val = line_number_of_data_notes_is_any_indicator(self,line_no)
            return_val =  self.line_number_of_data_notes_is_year_indicator(line_no)...
                          || self.line_number_of_data_notes_is_region_indicator(line_no)...
                          || self.line_number_of_data_notes_is_variable_indicator(line_no);
        end
        function return_val = line_number_of_data_notes_is_year_indicator(self,line_no)
            if line_no == length(self.data_notes)
                return_val = false;
                return;end
            is_4_digit_number = object_oriented_simcap.Utils.regexp_matches_entire_string(...
                self.data_notes{line_no},'^\d{4}$'...
            );
            has_correct_underline = strcmp(...
                self.data_notes{line_no+1},...
                repmat(...
                    self.DataWriter.data_notes_year_underline,...
                    1,length(self.data_notes{line_no})...
                )...
            );
            return_val = is_4_digit_number && has_correct_underline;
        end
        function return_val = line_number_of_data_notes_is_region_indicator(self,line_no)
            if line_no == length(self.data_notes)
                return_val = false;
                return;end
            is_valid_region = ismember(...
                self.data_notes{line_no},self.data.data_table.Region...
            );
            has_correct_underline = strcmp(...
                self.data_notes{line_no+1},...
                repmat(...
                    self.DataWriter.data_notes_region_underline,...
                    1,length(self.data_notes{line_no})...
                )...
            );
            return_val = is_valid_region && has_correct_underline;
        end
        function return_val = line_number_of_data_notes_is_variable_indicator(self,line_no)
            if line_no == length(self.data_notes)
                return_val = false;
                return;end
            is_valid_variable = ismember(...
                self.data_notes{line_no},self.data.data_table.Variable...
            );
            has_correct_underline = strcmp(...
                self.data_notes{line_no+1},...
                repmat(...
                    self.DataWriter.data_notes_variable_underline,...
                    1,length(self.data_notes{line_no})...
                )...
            );
            return_val = is_valid_variable && has_correct_underline;
        end
        
        function add_note_to_data_table_notes_cell(self,note,rows2addto)
            for i=find(rows2addto)'
                self.data_table_notes_cell{i}{end+1} = note;
            end
        end
    end
end