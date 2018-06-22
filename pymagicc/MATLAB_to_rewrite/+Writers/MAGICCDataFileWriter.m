classdef MAGICCDataFileWriter < handle
    properties
        data
    end
    properties (SetAccess = protected)
        notes_start_line = 'NOTES'
        notes_start_line_underline
        notes_end_line = '~~~endnotes~~~'
        general_data_notes_split_line = '================================='
        data_notes_year_underline = '~'
        data_notes_region_underline = '-'
        data_notes_variable_underline = '='

        THISFILE_DATACOLUMNS
        THISFILE_DATAROWS
        THISFILE_FIRSTYEAR
        THISFILE_LASTYEAR
        THISFILE_ANNUALSTEPS
        THISFILE_FIRSTDATAROW
        THISFILE_UNITS
        THISFILE_DATTYPE
        THISFILE_REGIONMODE

        MAGICC_DATTYPE_REGIONMODE_regions_table
    end
    properties (Access = protected)
        notes_start_line_underline_char = '~'

        file_id

        data_notes_struct
        data_notes_cell

        file_specifications_start_line = '&THISFILE_SPECIFICATIONS'
        file_specifications_end_line = '/'
        file_specifications_placeholder = '<file-specs-placeholder>'
        file_specifications_fields

        MAGICC_DATTYPE_REGIONMODE_regions_csv

        region_column_order

        newline_char = '\r\n'

        column_padding
        column_padding_minimum = 8

        DataTableManipulator = object_oriented_simcap.DataTableManipulators.MAGICCDataTableManipulator
    end
    methods
        function self = MAGICCDataFileWriter
            self.notes_start_line_underline = repmat(...
                self.notes_start_line_underline_char,...
                1,length(self.notes_start_line)...
            );
            self.MAGICC_DATTYPE_REGIONMODE_regions_csv = object_oriented_simcap.Utils.join_paths(...
                object_oriented_simcap.Utils.return_path_to_directory_containing_this_file,...
                '..','..','definitions',...
                'MAGICC_DATTYPE_REGIONMODE_regions.csv'...
            );
            self.load_MAGICC_DATTYPE_REGIONMODE_regions_csv_to_table
        end

        function file_specifications_fields = get.file_specifications_fields(self)
            properties_cell = properties(self);
            file_specifications_fields = properties_cell(...
                startsWith(properties_cell,'THISFILE')...
            );
        end

        function write_MAGICC_data_file(self)
            self.check_data
            self.file_id = fopen(self.data.full_path_file2write,'w+');
            self.write_file_header
            self.write_file_descriptor_fields
            self.write_file_notes
            self.write_file_THISFILE_SPECIFICATIONS_and_datablock
            fclose(self.file_id);
            disp([...
                'Wrote ' self.data.full_path_file2write...
            ])
        end
    end
    methods (Access = protected)
        function check_data(self)
            self.data.convert_to_MAGICC_variables
            self.data.convert_to_MAGICC_units
            self.data.check_regional_breakdowns
        end
        
        function write_file_header(self)
            fprintf(self.file_id,self.get_file_header);
            fprintf(self.file_id,repmat(self.newline_char,1,2));
        end
        function file_header_formatted = get_file_header(self)
            file_header = [...
                '.__  __          _____ _____ _____ _____ ______   _____       _______       ______ _____ _      ______ ' self.newline_char...
                '|  \/  |   /\   / ____|_   _/ ____/ ____|____  | |  __ \   /\|__   __|/\   |  ____|_   _| |    |  ____|' self.newline_char...
                '| \  / |  /  \ | |  __  | || |   | |        / /  | |  | | /  \  | |  /  \  | |__    | | | |    | |' self.newline_char...
                '| |\/| | / /\ \| | |_ | | || |   | |       / /   | |  | |/ /\ \ | | / /\ \ |  __|   | | | |    |  __|' self.newline_char...
                '| |  | |/ ____ \ |__| |_| || |___| |____  / /    | |__| / ____ \| |/ ____ \| |     _| |_| |____| |____' self.newline_char...
                '|_|  |_/_/    \_\_____|_____\_____\_____|/_/     |_____/_/    \_\_/_/    \_\_|    |_____|______|______|'...
            ];
            file_header_formatted = object_oriented_simcap.Utils.return_sprintf_compatible_string(...
                file_header...
            );
        end
        function number_format_code = get_number_format_code(self)
            number_format_code = '.8e';
        end

        function write_file_descriptor_fields(self)
            descriptor_fields = self.get_descriptor_fields;
            descriptor_strings = self.get_descriptor_strings;
            for i=1:length(descriptor_fields)
                if ~isprop(self.data,descriptor_fields{i})...
                   || isempty(self.data.(descriptor_fields{i}))
                    descriptor_value = self.return_descriptor_value_for_descriptor_field(...
                        descriptor_fields{i}...
                    );
                else
                    descriptor_value = self.data.(descriptor_fields{i});
                end
                str2write = [...
                    descriptor_strings{i}...
                    descriptor_value...
                    self.newline_char...
                ];
                self.write_sequence_to_file(str2write)
            end
            self.write_newline
        end
        function descriptor_fields = get_descriptor_fields(self)
            descriptor_fields = [...
                {'Data' 'Gas'} self.data.descriptor_fields...
            ];
        end
        function descriptor_strings = get_descriptor_strings(self)
            descriptor_strings = cellfun(...
                @(x) self.data.return_descriptor_string_from_descriptor_field(x),...
                self.get_descriptor_fields,...
                'UniformOutput',false...
            );
        end
        function descriptor_value = return_descriptor_value_for_descriptor_field(self,descriptor_field)
            if strcmp(descriptor_field,'Date')
                self.data.(descriptor_field) = datestr(now);
                descriptor_value = datestr(now);
            elseif strcmp(descriptor_field,'Gas')
                descriptor_value = self.return_Gas_descriptor;
            elseif strcmp(descriptor_field,'Data')
                descriptor_value = self.return_Data_descriptor;
            else
                self.data.(descriptor_field) = '';
            end
        end
        function Gas_descriptor = return_Gas_descriptor(self)
            unique_gases = unique(self.data.data_table.Variable);
            Gas_descriptor = strjoin(unique_gases,', ');
        end
        function Data_value = return_Data_descriptor(self)
            Data_value = 'MAGICC data file';
        end
        
        function write_file_notes(self)
            if self.are_no_notes
                return;end
            % push end up for code coverage
            self.write_file_notes_header
            self.write_general_notes
            self.write_general_notes_split
            self.write_data_notes
            self.write_file_notes_end
            self.write_newline
        end
        function return_val = are_no_notes(self)
            return_val = isempty(self.data.Notes)...
                         && all(cellfun(@isempty,self.data.data_table.Notes));
        end
        function write_file_notes_header(self)
            str2write = [...
                self.notes_start_line self.newline_char...
                self.notes_start_line_underline self.newline_char...
            ];
            self.write_sequence_to_file(str2write)
        end
        function write_general_notes(self)
            general_notes = strjoin(self.data.Notes,self.newline_char);
            self.write_sequence_to_file(general_notes)
            self.write_newline
        end
        function write_general_notes_split(self)
            self.write_sequence_to_file(self.general_data_notes_split_line)
            self.write_newline
        end

        function write_data_notes(self)
            self.data_notes_cell = self.data.data_table.Notes;
            self.sort_data_notes_cell
            self.write_sorted_data_notes
        end
        function sort_data_notes_cell(self)
            handled_notes = {};
            for note_cell = self.data_notes_cell'
                for note = note_cell{1}
                    if ~ismember(note{1},handled_notes)
                        self.sort_data_note(note{1})
                        handled_notes = [handled_notes note{1}];
                    end
                end
            end
        end
        function sort_data_note(self,note)
            data_row_idxs_note_applies_to = cellfun(...
                @(x) ismember(note,x),...
                self.data_notes_cell...
            );
            if all(data_row_idxs_note_applies_to)
                self.add_data_note_about_all(note)
                return
            else
                unsorted_note_idxs = data_row_idxs_note_applies_to;
            end

            unsorted_note_idxs = self.handle_note_unsorted_idxs_for_years_rtrn_unsorted_idxs(...
                note,...
                unsorted_note_idxs...
            );
            if ~any(unsorted_note_idxs)
                return;end
            % put end on previous line to help code coverage
            unsorted_note_idxs = self.handle_note_unsorted_idxs_for_regions_rtrn_unsorted_idxs(...
                note,...
                unsorted_note_idxs...
            );
            if ~any(unsorted_note_idxs)
                return;end
            % put end on previous line to help code coverage
            unsorted_note_idxs = self.handle_note_unsorted_idxs_for_variables_rtrn_unsorted_idxs(...
                note,...
                unsorted_note_idxs...
            );
            if any(unsorted_note_idxs)
                % I haven't worked out a way to test this error, maybe it's
                % impossible to get to this point..
                error('You have unsorted notes...');end
            % put end on previous line to help code coverage
        end
        function add_data_note_about_all(self,note)
            if ~isfield(self.data_notes_struct,'all')
                self.data_notes_struct.all = {note};
            else
                self.data_notes_struct.all{end+1} = note;
            end
        end
        function add_data_note_about_year(self,note,year)
            year_field = self.return_number_as_field(year);
            try
                self.data_notes_struct.year_notes.(year_field).all{end+1} = note;
            catch
                self.data_notes_struct.year_notes.(year_field).all = {note};
            end
        end
        function add_data_note_about_region(self,note,region)
            try
                self.data_notes_struct.region_notes.(region).all{end+1} = note;
            catch
                self.data_notes_struct.region_notes.(region).all = {note};
            end
        end
        function add_data_note_about_region_year(self,note,region,year)
            year_field = self.return_number_as_field(year);
            try
                self.data_notes_struct.region_notes.(region).(year_field).all{end+1} = note;
            catch
                self.data_notes_struct.region_notes.(region).(year_field).all = {note};
            end
        end
        function add_data_note_about_variable(self,note,variable)
            try
                self.data_notes_struct.variable_notes.(variable).all{end+1} = note;
            catch
                self.data_notes_struct.variable_notes.(variable).all = {note};
            end
        end
        function add_data_note_about_variable_region(self,note,variable,region)
            try
                self.data_notes_struct.variable_notes.(variable).region_notes.(region).all{end+1} = note;
            catch
                self.data_notes_struct.variable_notes.(variable).region_notes.(region).all = {note};
            end
        end
        function add_data_note_about_variable_year(self,note,variable,year)
            year_field = self.return_number_as_field(year);
            try
                self.data_notes_struct.variable_notes.(variable).year_notes.(year_field).all{end+1} = note;
            catch
                self.data_notes_struct.variable_notes.(variable).year_notes.(year_field).all = {note};
            end
        end
        function add_data_note_about_variable_region_year(self,note,variable,region,year)
            year_field = self.return_number_as_field(year);
            try
                self.data_notes_struct.variable_notes.(variable).region_notes.(region).(region).(year_field).all{end+1} = note;
            catch
                self.data_notes_struct.variable_notes.(variable).region_notes.(region).(year_field).all = {note};
            end
        end
        function field_name = return_number_as_field(self,number)
             field_name = ['x' num2str(number)];
        end
        function number = return_number_string_from_number_field(self,number_field)
             number = number_field(2:end);
        end

        % these are a mess, not sure how to fix them right now
        % I should be able to do the combination more easily but can't
        % work out how right now

        % In short I want to check, for each note, whether it applies to
        % all the data, all the data of a given variable, all the data of a
        % given region, all the data of a given year, all the data of a
        % given variable and year, all the data of a given region and year,
        % all the data of a given variable and region or all the data of a
        % given variable, region and year and sort it appropriately.
        function unsorted_note_idxs = handle_note_unsorted_idxs_for_years_rtrn_unsorted_idxs(self,note,unsorted_note_idxs)
            unsorted_note_idxs_values = find(unsorted_note_idxs);
            years_note_applies_to = unique(self.data.data_table.Year(...
                unsorted_note_idxs...
            ));
            for year = object_oriented_simcap.Utils.convert_to_row_vector(years_note_applies_to)
                year_idx_values = find(self.data.data_table.Year == year);
                if all(ismember(year_idx_values,unsorted_note_idxs_values))
                    self.add_data_note_about_year(note,year)
                    unsorted_note_idxs(year_idx_values) = false;
                end
            end
        end
        function unsorted_note_idxs = handle_note_unsorted_idxs_for_regions_rtrn_unsorted_idxs(self,note,unsorted_note_idxs)
            unsorted_note_idxs_values = find(unsorted_note_idxs);
            regions_note_applies_to = unique(self.data.data_table.Region(...
                unsorted_note_idxs...
            ));
            for region = object_oriented_simcap.Utils.convert_to_row_vector(regions_note_applies_to)
                region_idx_values = find(strcmp(...
                    self.data.data_table.Region,...
                    region{1}...
                ));
                if all(ismember(region_idx_values,unsorted_note_idxs_values))
                    self.add_data_note_about_region(note,region{1})
                    unsorted_note_idxs(region_idx_values) = false;
                else
                    years_note_applies_to = unique(self.data.data_table.Year(...
                        unsorted_note_idxs...
                    ));
                    for year = object_oriented_simcap.Utils.convert_to_row_vector(years_note_applies_to)
                        year_idx_values = find(self.data.data_table.Year == year);
                        region_year_idx_values = intersect(...
                            region_idx_values,...
                            year_idx_values...
                        );
                        if all(ismember(region_year_idx_values,unsorted_note_idxs_values))
                            self.add_data_note_about_region_year(note,region{1},year)
                            unsorted_note_idxs(region_year_idx_values) = false;
                        end
                    end
                end
            end
        end
        function unsorted_note_idxs = handle_note_unsorted_idxs_for_variables_rtrn_unsorted_idxs(self,note,unsorted_note_idxs)
            unsorted_note_idxs_values = find(unsorted_note_idxs);
            variables_note_applies_to = unique(self.data.data_table.Variable(...
                unsorted_note_idxs...
            ));
            for variable = object_oriented_simcap.Utils.convert_to_row_vector(variables_note_applies_to)
                variable_idx_values = find(strcmp(...
                    self.data.data_table.Variable,...
                    variable{1}...
                ));
                if all(ismember(variable_idx_values,unsorted_note_idxs_values))
                    self.add_data_note_about_variable(note,variable{1})
                    unsorted_note_idxs(variable_idx_values) = false;
                else
                    years_note_applies_to = unique(self.data.data_table.Year(...
                        unsorted_note_idxs...
                    ));
                    for year = object_oriented_simcap.Utils.convert_to_row_vector(years_note_applies_to)
                        year_idx_values = find(self.data.data_table.Year == year);
                        variable_year_idx_values = intersect(...
                            variable_idx_values,...
                            year_idx_values...
                        );
                        if all(ismember(variable_year_idx_values,unsorted_note_idxs_values))
                            self.add_data_note_about_variable_year(note,variable{1},year)
                            unsorted_note_idxs(variable_year_idx_values) = false;
                        end
                    end
                    regions_note_applies_to = unique(self.data.data_table.Region(...
                        unsorted_note_idxs...
                    ));
                    for region = regions_note_applies_to'
                        region_idx_values = find(strcmp(...
                            self.data.data_table.Region,...
                            region{1}...
                        ));
                        variable_region_idx_values = intersect(...
                            variable_idx_values,...
                            region_idx_values...
                        );
                        if all(ismember(variable_region_idx_values,unsorted_note_idxs_values))
                            self.add_data_note_about_variable_region(note,variable{1},region{1})
                            unsorted_note_idxs(variable_region_idx_values) = false;
                        else
                            years_note_applies_to = unique(self.data.data_table.Year(...
                                unsorted_note_idxs...
                            ));
                            for year = years_note_applies_to'
                                year_idx_values = find(self.data.data_table.Year == year);
                                variable_region_year_idx_values = intersect(...
                                    variable_region_idx_values,...
                                    year_idx_values...
                                );
                                if all(ismember(variable_region_year_idx_values,unsorted_note_idxs_values))
                                    year_string = num2str(year);
                                    self.add_data_note_about_variable_region_year(note,variable{1},region{1},year)
                                    unsorted_note_idxs(variable_region_year_idx_values) = false;
                                end
                            end
                        end
                    end
                end
            end
        end

        function write_sorted_data_notes(self)
            if isfield(self.data_notes_struct,'all')
                self.write_notes_in_notes_cell(self.data_notes_struct.all)
            end
            if isfield(self.data_notes_struct,'year_notes')
                self.write_year_notes_in_struct(...
                    self.data_notes_struct.year_notes...
                )
            end
            if isfield(self.data_notes_struct,'region_notes')
                self.write_region_notes_in_struct(...
                    self.data_notes_struct.region_notes...
                )
            end
            if isfield(self.data_notes_struct,'variable_notes')
                self.write_variable_notes_in_struct(...
                    self.data_notes_struct.variable_notes...
                )
            end
        end
        function write_variable_notes_in_struct(self,variable_notes_struct)
            for variable_field = fields(variable_notes_struct)'
                self.write_variable_header_for_variable(variable_field{1})
                if isfield(variable_notes_struct.(variable_field{1}),'all')
                    self.write_notes_in_notes_cell(...
                        variable_notes_struct.(variable_field{1}).all...
                    )
                end
                if isfield(variable_notes_struct.(variable_field{1}),'year_notes')
                    self.write_year_notes_in_struct(...
                        variable_notes_struct.(variable_field{1}).year_notes...
                    )
                end
                if isfield(variable_notes_struct.(variable_field{1}),'region_notes')
                    self.write_region_notes_in_struct(...
                        variable_notes_struct.(variable_field{1}).region_notes...
                    )
                end
            end
        end
        function write_variable_header_for_variable(self,variable)
            self.write_raw_text_to_file_with_newline(variable)
            self.write_raw_text_to_file_with_newline(repmat(...
                self.data_notes_variable_underline,...
                1,length(variable)...
            ))
        end
        function write_region_notes_in_struct(self,region_notes_struct)
            for region_field = fields(region_notes_struct)'
                self.write_region_header_for_region(region_field{1})
                if isfield(region_notes_struct.(region_field{1}),'all')
                    self.write_notes_in_notes_cell(...
                        region_notes_struct.(region_field{1}).all...
                    )
                end
                self.write_year_notes_in_struct(...
                    region_notes_struct.(region_field{1})...
                )
            end
        end
        function write_region_header_for_region(self,region)
            self.write_raw_text_to_file_with_newline(region)
            self.write_raw_text_to_file_with_newline(repmat(...
                self.data_notes_region_underline,...
                1,length(region)...
            ))
        end
        function write_year_notes_in_struct(self,year_notes_struct)
            for year_field = fields(year_notes_struct)'
                if strcmp(year_field,'all')
                    continue;end
                % put end on previous line to help code coverage analysis
                year_string = self.return_number_string_from_number_field(...
                    year_field{1}...
                );
                self.write_year_header_for_year_string(year_string)
                self.write_notes_in_notes_cell(...
                    year_notes_struct.(year_field{1}).all...
                )
            end
        end
        function write_year_header_for_year_string(self,year_string)
            self.write_raw_text_to_file_with_newline(year_string)
            self.write_raw_text_to_file_with_newline(repmat(...
                self.data_notes_year_underline,...
                1,length(year_string)...
            ))
        end
        function write_notes_in_notes_cell(self,notes_cell)
            for line = notes_cell
                self.write_raw_text_to_file_with_newline(line{1})
            end
            self.write_newline
        end

        function write_file_notes_end(self)
            self.write_sequence_to_file([self.notes_end_line self.newline_char])
        end


        function write_file_THISFILE_SPECIFICATIONS_and_datablock(self)
            self.write_THISFILE_SPECIFICATIONS_placeholders
            self.write_datablock_and_update_THISFILE_SPECIFICATIONS
            self.write_THISFILE_SPECIFICATIONS_values
        end

        function write_THISFILE_SPECIFICATIONS_placeholders(self)
            self.write_sequence_to_file([...
                self.file_specifications_start_line self.newline_char...
            ])
            for field2write = self.file_specifications_fields'
                pad_width = max(strlength(self.file_specifications_fields))+5;
                str2write = [...
                    ' ' pad(field2write{1},pad_width) ' = '...
                    self.file_specifications_placeholder ...
                    ' ,' self.newline_char...
                ];
                self.write_sequence_to_file([...
                    str2write...
                ])
            end
            self.write_sequence_to_file([...
                self.file_specifications_end_line...
                self.newline_char self.newline_char...
            ])
        end

        function write_datablock_and_update_THISFILE_SPECIFICATIONS(self)
            self.set_data_table_relevant_THISFILE_SPECIFICATIONS
            cell_datablock = self.DataTableManipulator.convert_long_data_table_to_wide_and_return(...
                self.data...
            );
            updated_cell_datablock = self.return_renamed_reordered_cell_datablock(...
                cell_datablock...
            );
            self.write_cell_datablock_to_file_and_update_THISFILE_SPECIFICATIONS(updated_cell_datablock)
        end
        function set_data_table_relevant_THISFILE_SPECIFICATIONS(self)
            self.set_THISFILE_UNITS
            self.set_THISFILE_DATTYPE_THISFILE_REGIONMODE_region_column_order
        end
        function set_THISFILE_UNITS(self)
            unique_units = unique(self.data.data_table.Unit);
            if length(unique_units) == 1
                self.THISFILE_UNITS = unique_units{1};
            else
                self.THISFILE_UNITS = 'MISC';
            end
        end
        function set_THISFILE_DATTYPE_THISFILE_REGIONMODE_region_column_order(self)
            unique_regions = unique(self.data.data_table.Region);
            matching_regions_row = cellfun(...
                @(x) object_oriented_simcap.Utils.contain_same_elements(x,unique_regions),...
                self.MAGICC_DATTYPE_REGIONMODE_regions_table.Regions...
            );

            self.THISFILE_DATTYPE = self.MAGICC_DATTYPE_REGIONMODE_regions_table.THISFILE_DATTYPE{...
                matching_regions_row...
            };
            self.THISFILE_REGIONMODE = self.MAGICC_DATTYPE_REGIONMODE_regions_table.THISFILE_REGIONMODE{...
                matching_regions_row...
            };
            self.region_column_order = self.MAGICC_DATTYPE_REGIONMODE_regions_table.Regions{...
                matching_regions_row...
            };
        end

        function updated_cell_datablock = return_renamed_reordered_cell_datablock(self,cell_datablock)
            renamed_cell_datablock = self.return_renamed_cell_datablock(cell_datablock);
            updated_cell_datablock = self.return_reordered_cell_datablock(renamed_cell_datablock);
        end
        function renamed_cell_datablock = return_renamed_cell_datablock(self,cell_datablock)
            renamed_cell_datablock = cell_datablock;
            variable_idx = strcmpi(renamed_cell_datablock,'Variable');
            renamed_cell_datablock{variable_idx} = 'VARIABLE';
            unit_idx = strcmpi(renamed_cell_datablock,'Unit');
            renamed_cell_datablock{unit_idx} = 'UNITS';
            region_idx = strcmpi(renamed_cell_datablock,'Region');
            renamed_cell_datablock{region_idx} = 'YEARS';
        end
        function updated_cell_datablock = return_reordered_cell_datablock(self,renamed_cell_datablock)
            region_reordered_cell_datablock = self.return_region_reordered_cell_datablock(...
                renamed_cell_datablock...
            );
            updated_cell_datablock = self.return_header_row_reordered_cell_datablock(...
                region_reordered_cell_datablock...
            );
        end
        function region_reordered_cell_datablock = return_region_reordered_cell_datablock(self,renamed_cell_datablock)
            region_reordered_cell_datablock = renamed_cell_datablock;
            for i=1:length(self.region_column_order)
                columns_to_take = any(...
                    strcmp(...
                        renamed_cell_datablock,...
                        self.region_column_order{i}...
                    ),...
                    1 ...
                );
                columns_to_replace = i+1:i+sum(columns_to_take);
                replacement_columns = renamed_cell_datablock(...
                    :,...
                    columns_to_take...
                );
                region_reordered_cell_datablock(:,columns_to_replace) = replacement_columns;
            end
        end
        function updated_cell_datablock = return_header_row_reordered_cell_datablock(self,region_reordered_cell_datablock)
            updated_cell_datablock = region_reordered_cell_datablock;
            for i=1:length(self.get_header_row_order)
                row_to_take = strcmp(...
                    region_reordered_cell_datablock(:,1),...
                    self.get_header_row_order{i}...
                );
                updated_cell_datablock(i,:) = region_reordered_cell_datablock(...
                    row_to_take,:...
                );
            end
        end
        function header_row_order = get_header_row_order(self)
            header_row_order = {'VARIABLE' 'TODO' 'UNITS' 'YEARS'};
        end

        function write_cell_datablock_to_file_and_update_THISFILE_SPECIFICATIONS(self,updated_cell_datablock)
            numeric_row_idxs = all(...
                cellfun(@isnumeric,updated_cell_datablock)...
                ,2 ...
            );
            header_rows = updated_cell_datablock(~numeric_row_idxs,:);
            self.write_datablock_header_rows(header_rows)
            self.set_THISFILE_FIRSTDATAROW
            numeric_rows = cell2mat(updated_cell_datablock(numeric_row_idxs,:));
            self.THISFILE_DATACOLUMNS = size(numeric_rows,2) - 1;
            self.THISFILE_DATAROWS = size(numeric_rows,1);
            self.THISFILE_FIRSTYEAR = numeric_rows(1,1);
            self.THISFILE_LASTYEAR = numeric_rows(end,1);
            self.THISFILE_ANNUALSTEPS = floor(...
                self.THISFILE_DATAROWS...
                / (self.THISFILE_LASTYEAR-self.THISFILE_FIRSTYEAR+1)...
            );
            self.write_datablock_numeric_rows(numeric_rows)
        end
        function write_datablock_header_rows(self,header_rows)
            self.column_padding = max([...
                max(strlength(header_rows(:))) + 6 ...
                self.return_numeric_column_width  + 6 ...
                self.column_padding_minimum...
            ]);
            for header_row = header_rows'
                padded_row = pad(...
                    header_row',...
                    self.column_padding,...
                    'left'...
                );
                self.write_sequence_to_file([...
                    strjoin(padded_row,'') self.newline_char...
                ]);
            end
        end
        function numeric_column_width = return_numeric_column_width(self)
            decimal_points_cell = regexp(...
                self.get_number_format_code,...
                '(?<=\.)(\d*)(?=\w)',...
                'match'...
            );
            decimal_points = str2double(decimal_points_cell{1});
            if contains(self.get_number_format_code,'e')
                numeric_column_width = decimal_points + 6;
            elseif contains(self.get_number_format_code,'f')
                numeric_column_width = decimal_points + 2;
            else
                error([...
                    'I don''t know how to read this number_format_code: '...
                    self.get_number_format_code...
                ])
            end
        end
        function set_THISFILE_FIRSTDATAROW(self)
            current_text = self.return_current_text;
            self.THISFILE_FIRSTDATAROW = length(current_text) + 1;
        end
        function current_text = return_current_text(self)
            frewind(self.file_id);
            current_text_cell = textscan(...
                self.file_id,...
                '%s',...
                'whitespace', '',...
                'delimiter',self.newline_char...
            );
            current_text = current_text_cell{1};
        end
        function write_datablock_numeric_rows(self,numeric_rows)
            year_column_format = ['%' num2str(self.column_padding) 'i'];
            timeseries_column_format = repmat(...
                ['%' num2str(self.column_padding) self.get_number_format_code],...
                1,(size(numeric_rows,2)-1)...
            );
            format_statement = [...
                year_column_format...
                timeseries_column_format...
                self.newline_char...
            ];
            fprintf(self.file_id,format_statement,numeric_rows');
        end

        function write_THISFILE_SPECIFICATIONS_values(self)
            current_text = self.return_current_text;
            updated_text = current_text;
            for field2write = self.file_specifications_fields'
                line_of_interest_idx = contains(...
                    current_text,...
                    field2write{1}...
                );
                value_string = self.return_formatted_THISFILE_SPECIFICATIONS_value(...
                    self.(field2write{1})...
                );
                updated_text(line_of_interest_idx) = replace(...
                    current_text(line_of_interest_idx),...
                    self.file_specifications_placeholder,...
                    value_string...
                );
            end
            fclose(self.file_id);
            self.file_id = fopen(self.data.full_path_file2write,'w+');
            updated_text2write = replace(updated_text,{'\' '%'},{'\\' '%%'});
            self.write_sequence_to_file(strjoin(updated_text2write,self.newline_char))
        end
        function formatted_value = return_formatted_THISFILE_SPECIFICATIONS_value(self,in_value)
            if ischar(in_value)
                formatted_value = ['"' in_value '"'];
            else
                formatted_value = num2str(in_value);
            end
        end

        function write_sequence_to_file(self,sequence2write)
            fprintf(...
                self.file_id,...
                sequence2write...
            );
        end
        function write_raw_text_to_file_with_newline(self,text2write)
            fprintf(...
                self.file_id,...
                '%s',text2write...
            );
            self.write_newline
        end
        function write_newline(self)
            self.write_sequence_to_file(self.newline_char)
        end

        function load_MAGICC_DATTYPE_REGIONMODE_regions_csv_to_table(self)
            self.MAGICC_DATTYPE_REGIONMODE_regions_table = return_MAGICC_DATTYPE_REGIONMODE_regions_table_from_csv(...
                self.MAGICC_DATTYPE_REGIONMODE_regions_csv...
            );
            function out_table = return_MAGICC_DATTYPE_REGIONMODE_regions_table_from_csv(MAGICC_DATTYPE_REGIONMODE_regions_csv)
                raw_table = readtable(...
                    MAGICC_DATTYPE_REGIONMODE_regions_csv,...
                    'ReadVariableNames',true...
                );
                region_columns = startsWith(...
                    raw_table.Properties.VariableNames,...
                    'Region'...
                );
                out_table = raw_table(:,~region_columns);
                valid_region_columns = region_columns ...
                                       & varfun(...
                                             @iscell,...
                                             raw_table,...
                                             'OutputFormat','uniform'...
                                       );
                out_table.Regions = rowfun(...
                    @(x) x(~cellfun(@isempty,x)),...
                    raw_table(:,valid_region_columns),...
                    'SeparateInputs',false,...
                    'OutputFormat','cell'...
                );
            end
        end
    end
end
