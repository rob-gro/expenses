import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import datetime
import zipfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import smtplib
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from app.database.db_manager import DBManager
from app.config import Config
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
import os
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Set seaborn style for better visualizations
sns.set(style="whitegrid")

def generate_report(db_manager, category=None, start_date=None, end_date=None,
                    group_by='month', format_type='excel'):
    """
    Generate expense report based on parameters
    Returns a tuple of (file_path, report_type, format_type)
    """
    try:
        # Get report data from database
        report_data = db_manager.get_expense_data_for_report(
            category=category,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by
        )

        # Generate report name
        report_name = f"expense_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Determine report type
        report_type = "Category_Report" if category else "Full_Expense_Report"
        if start_date and end_date:
            report_type += f"_{start_date}_to_{end_date}"

        # Create DataFrame from grouped data
        grouped_df = pd.DataFrame(report_data['grouped'])
        detailed_df = pd.DataFrame(report_data['detailed'])

        # Log data stats for debugging
        logger.info(f"Report data - Grouped rows: {len(grouped_df)}, Detailed rows: {len(detailed_df)}")
        if not grouped_df.empty:
            logger.info(f"Grouped columns: {grouped_df.columns.tolist()}")
            if 'total_amount' in grouped_df.columns:
                logger.info(f"Total amount sum: {grouped_df['total_amount'].sum()}")

        # Ensure we have data
        if grouped_df.empty:
            logger.warning(f"No data found for report with category={category}, start_date={start_date}, end_date={end_date}")
            # Create empty DataFrames with correct columns
            grouped_df = pd.DataFrame(
                columns=['period', 'period_label', 'category', 'total_amount', 'transaction_count'])
            detailed_df = pd.DataFrame(columns=['id', 'date', 'amount', 'vendor', 'category', 'description'])

        # Create visualizations
        chart_paths = create_visualizations(grouped_df, report_name, category)

        # Generate report based on format type
        if format_type.lower() == 'excel':
            file_path = generate_excel_report(grouped_df, detailed_df, chart_paths, report_name, category)
        elif format_type.lower() == 'csv':
            file_path = generate_csv_report(grouped_df, detailed_df, report_name)
        elif format_type.lower() == 'pdf':
            file_path = generate_pdf_report(grouped_df, detailed_df, chart_paths, report_name, category)
        else:
            # Default to Excel
            file_path = generate_excel_report(grouped_df, detailed_df, chart_paths, report_name, category)
            format_type = 'excel'

        logger.info(f"Report generated successfully: {file_path}")
        return file_path, report_type, format_type

    except Exception as e:
        logger.error(f"Error generating report: {str(e)}", exc_info=True)
        raise


def create_visualizations(df, report_name, category=None):
    """Create visualizations for the report and save them to files"""
    chart_paths = {}

    # Skip visualization creation if DataFrame is empty
    if df.empty:
        logger.warning("Skipping visualizations - DataFrame is empty")
        return chart_paths

    try:
        # Create directory for charts
        config = Config()

        # Create directory for charts
        chart_dir = os.path.join(config.REPORT_FOLDER, 'charts')
        os.makedirs(chart_dir, exist_ok=True)

        # 1. Spending over time chart (line chart)
        if 'period_label' in df.columns and 'total_amount' in df.columns:
            # Sprawdź, czy mamy dane liczbowe dla wykresów
            if df['total_amount'].sum() > 0 and df['total_amount'].notna().sum() > 0:
                # Logowanie danych do diagnozy
                logger.info(f"Creating time chart. Data shape: {df.shape}")
                logger.info(f"Period labels: {df['period_label'].unique().tolist()}")
                logger.info(f"Total amount sum: {df['total_amount'].sum()}")

                # If we have multiple categories, create a grouped line chart
                if category is None:
                    pivot_df = df.pivot(index='period_label', columns='category', values='total_amount')
                    logger.info(f"Pivot table shape: {pivot_df.shape if not pivot_df.empty else 'Empty'}")

                    if not pivot_df.empty and pivot_df.size > 0 and pivot_df.notna().sum().sum() > 0:
                        try:
                            # Użyj backendu Agg dla matplotlib
                            import matplotlib
                            matplotlib.use('Agg')

                            # Stwórz figurę
                            fig = plt.figure(figsize=(10, 6))
                            ax = fig.add_subplot(111)

                            # Narysuj wykres
                            pivot_df.plot(kind='line', marker='o', ax=ax)

                            ax.set_title('Spending Over Time')
                            ax.set_xlabel('Period')
                            ax.set_ylabel('Amount (£)')
                            plt.xticks(rotation=45)
                            plt.tight_layout()

                            time_chart_path = os.path.join(chart_dir, f"{report_name}_time_chart.png")
                            plt.savefig(time_chart_path)
                            plt.close(fig)
                            chart_paths['time_chart'] = time_chart_path
                            logger.info("Multi-category time chart created successfully")
                        except Exception as e:
                            logger.error(f"Error creating multi-category time chart: {str(e)}", exc_info=True)
                    else:
                        logger.warning("Skipping multi-category time chart - insufficient data in pivot table")
                else:
                    # Grupowanie i sortowanie według zdefiniowanego klucza chronologicznego
                    def period_to_sortable(period):
                        if '-' in period:
                            parts = period.split('-')
                            if len(parts) == 2:  # Format YYYY-WW (rok-tydzień)
                                year, week = parts
                                # Upewnij się, że tydzień jest numeryczny dla poprawnego sortowania
                                try:
                                    return f"{year}-{int(week):02d}"
                                except ValueError:
                                    pass
                        return period

                    # Grupowanie według period_label
                    grouped = df.groupby('period_label')['total_amount'].sum()

                    # Utworzenie nowego Series z posortowanymi indeksami
                    sorted_indices = sorted(grouped.index, key=period_to_sortable)
                    time_series = pd.Series([grouped[i] for i in sorted_indices], index=sorted_indices)
                    logger.info(f"Time series data for category '{category}': {time_series.to_dict()}")

                    if len(time_series) > 0:
                        try:
                            # Użyj backendu Agg dla matplotlib
                            import matplotlib
                            matplotlib.use('Agg')

                            # Upewnij się, że dane są liczbowe
                            time_series = time_series.astype(float)

                            # Stwórz figurę
                            fig = plt.figure(figsize=(10, 6))
                            ax = fig.add_subplot(111)

                            # Narysuj wykres
                            time_series.plot(kind='line', marker='o', color='blue', ax=ax)

                            ax.set_title('Spending Over Time')
                            ax.set_xlabel('Period')
                            ax.set_ylabel('Amount (£)')
                            plt.xticks(rotation=45)
                            plt.tight_layout()

                            time_chart_path = os.path.join(chart_dir, f"{report_name}_time_chart.png")
                            plt.savefig(time_chart_path)
                            plt.close(fig)
                            chart_paths['time_chart'] = time_chart_path
                            logger.info(f"Successfully created time chart for category '{category}'")
                        except Exception as e:
                            logger.error(f"Error creating time chart: {str(e)}", exc_info=True)
                    else:
                        logger.warning(f"No time series data available for category '{category}'")
            else:
                logger.warning("Skipping time chart - insufficient numeric data")

        # 2. Category breakdown chart (pie chart)
        if 'category' in df.columns and 'total_amount' in df.columns:
            category_totals = df.groupby('category')['total_amount'].sum()
            logger.info(f"Category totals: {category_totals.to_dict()}")

            # Only create pie chart if we have valid data
            if len(category_totals) > 1 and category_totals.sum() > 0:
                try:
                    matplotlib.use('Agg')

                    # Stwórz figurę
                    fig = plt.figure(figsize=(10, 8))
                    ax = fig.add_subplot(111)

                    # Narysuj wykres kołowy
                    wedges, texts, autotexts = ax.pie(
                        category_totals,
                        labels=category_totals.index,
                        autopct='%1.1f%%',
                        startangle=90,
                        shadow=True
                    )

                    ax.set_title('Expense Distribution by Category')
                    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle

                    category_chart_path = os.path.join(chart_dir, f"{report_name}_category_chart.png")
                    plt.savefig(category_chart_path)
                    plt.close(fig)
                    chart_paths['category_chart'] = category_chart_path
                    logger.info("Category pie chart created successfully")
                except Exception as e:
                    logger.error(f"Error creating category chart: {str(e)}", exc_info=True)
            else:
                logger.warning("Skipping category chart - insufficient data")

        # 3. Monthly comparison chart (bar chart)
        if 'period_label' in df.columns and 'total_amount' in df.columns:
            # Check if we have valid data for bar chart
            if df['total_amount'].sum() > 0 and df['period_label'].nunique() > 0:
                try:
                    # Użyj backendu Agg dla matplotlib
                    matplotlib.use('Agg')

                    # Stwórz figurę
                    fig = plt.figure(figsize=(12, 7))
                    ax = fig.add_subplot(111)

                    # Create a pivot table with periods as index and categories as columns
                    if category is None:
                        pivot_df = df.pivot_table(
                            index='period_label',
                            columns='category',
                            values='total_amount',
                            aggfunc='sum'
                        )
                        if not pivot_df.empty and pivot_df.size > 0 and pivot_df.notna().sum().sum() > 0:
                            pivot_df.plot(kind='bar', stacked=True, ax=ax)
                            logger.info("Created stacked bar chart for multiple categories")
                        else:
                            logger.warning("Skipping comparison chart - insufficient pivot data")
                            return chart_paths
                    else:
                        # Grupowanie według period_label
                        grouped = df.groupby('period_label')['total_amount'].sum()

                        # Utworzenie nowego Series z posortowanymi indeksami
                        sorted_indices = sorted(grouped.index, key=period_to_sortable)
                        monthly_totals = pd.Series([grouped[i] for i in sorted_indices], index=sorted_indices)

                        # Dodaj jawną konwersję do float dla wartości
                        monthly_totals = monthly_totals.astype(float)

                        logger.info(f"Monthly totals data type: {type(monthly_totals.iloc[0])}")
                        logger.info(f"Monthly totals values: {monthly_totals.to_dict()}")

                        if len(monthly_totals) > 0 and monthly_totals.sum() > 0:
                            monthly_totals.plot(kind='bar', color='skyblue', ax=ax)
                            logger.info(f"Created bar chart for category '{category}'")
                        else:
                            logger.warning(f"Skipping comparison chart - insufficient data for category '{category}'")
                            return chart_paths

                    ax.set_title('Expense Comparison by Period')
                    ax.set_xlabel('Period')
                    ax.set_ylabel('Amount (£)')
                    plt.xticks(rotation=45)
                    plt.tight_layout()

                    comparison_chart_path = os.path.join(chart_dir, f"{report_name}_comparison_chart.png")
                    plt.savefig(comparison_chart_path)
                    plt.close(fig)
                    chart_paths['comparison_chart'] = comparison_chart_path
                except Exception as e:
                    logger.error(f"Error creating comparison chart: {str(e)}", exc_info=True)
            else:
                logger.warning("Skipping comparison chart - insufficient data")

        return chart_paths

    except Exception as e:
        logger.error(f"Error creating visualizations: {str(e)}", exc_info=True)
        return {}
def generate_excel_report(grouped_df, detailed_df, chart_paths, report_name, category=None):
    """Generate Excel report with multiple sheets and embedded charts"""
    try:
        config = Config()

        # Create Excel writer
        report_path = os.path.join(config.REPORT_FOLDER, f"{report_name}.xlsx")

        # Create a Pandas Excel writer using XlsxWriter engine
        with pd.ExcelWriter(report_path, engine='xlsxwriter') as writer:
            # Write summary sheet
            grouped_df.to_excel(writer, sheet_name='Summary', index=False)

            # Write detailed data sheet
            detailed_df.to_excel(writer, sheet_name='Detailed Expenses', index=False)

            # Get the xlsxwriter workbook and worksheet objects
            workbook = writer.book
            summary_worksheet = writer.sheets['Summary']

            # Define formats
            title_format = workbook.add_format({
                'bold': True,
                'font_size': 16,
                'align': 'center',
                'valign': 'vcenter'
            })

            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D0D0D0',
                'border': 1
            })

            # Add title to summary sheet
            report_title = f"Expense Report"
            if category:
                report_title += f" - Category: {category}"

            summary_worksheet.merge_range('A1:F1', report_title, title_format)

            # Add charts to the Excel file if available
            if chart_paths:
                charts_sheet = workbook.add_worksheet('Charts')

                # Add each chart to the sheet
                row_position = 1
                for chart_name, chart_path in chart_paths.items():
                    # Add chart title
                    charts_sheet.merge_range(f'A{row_position}:H{row_position}',
                                             f"{chart_name.replace('_', ' ').title()}",
                                             title_format)
                    row_position += 1

                    # Insert image
                    charts_sheet.insert_image(f'A{row_position}', chart_path,
                                              {'x_scale': 0.8, 'y_scale': 0.8})

                    # Move to next position (allow space for chart)
                    row_position += 20

            # Format the summary sheet
            for col_num, value in enumerate(grouped_df.columns.values):
                summary_worksheet.write(1, col_num, value, header_format)

        return report_path

    except Exception as e:
        logger.error(f"Error generating Excel report: {str(e)}", exc_info=True)
        raise

def generate_csv_report(grouped_df, detailed_df, report_name):
    """Generate CSV report files"""
    try:
        config = Config()  # Już istnieje, ale musisz używać tej instancji

        # Create directory for the report
        report_dir = os.path.join(config.REPORT_FOLDER, report_name)  # Użyj instancji
        os.makedirs(report_dir, exist_ok=True)

        # Save summary data
        summary_path = os.path.join(report_dir, f"{report_name}_summary.csv")
        grouped_df.to_csv(summary_path, index=False)

        # Save detailed data
        detailed_path = os.path.join(report_dir, f"{report_name}_detailed.csv")
        detailed_df.to_csv(detailed_path, index=False)

        # Create a simple README file explaining the CSV files
        readme_path = os.path.join(report_dir, "README.txt")
        with open(readme_path, 'w') as f:
            f.write(f"Expense Report CSV Files\n")
            f.write(f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Files included:\n")
            f.write(f"1. {report_name}_summary.csv - Summarized expense data grouped by period\n")
            f.write(f"2. {report_name}_detailed.csv - Detailed expense data with individual transactions\n")

        # Create a zip file containing all CSV files
        zip_path = os.path.join(config.REPORT_FOLDER, f"{report_name}.zip")  # Użyj instancji
        with zipfile.ZipFile(zip_path, 'w') as zip_file:
            zip_file.write(summary_path, os.path.basename(summary_path))
            zip_file.write(detailed_path, os.path.basename(detailed_path))
            zip_file.write(readme_path, os.path.basename(readme_path))

        return zip_path

    except Exception as e:
        logger.error(f"Error generating CSV report: {str(e)}", exc_info=True)
        raise

def generate_pdf_report(grouped_df, detailed_df, chart_paths, report_name, category=None):
    """Generate professional PDF report with data tables and charts"""
    try:
        config = Config()

        # Create PDF file path
        pdf_path = os.path.join(config.REPORT_FOLDER, f"{report_name}.pdf")

        # Create the PDF document with custom styling
        doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                                leftMargin=36, rightMargin=36,
                                topMargin=36, bottomMargin=36)

        # Define styles
        styles = getSampleStyleSheet()

        # Create custom styles
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Title'],
            fontSize=18,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#0056b3'),
            spaceAfter=12
        )

        heading_style = ParagraphStyle(
            'Heading',
            parent=styles['Heading2'],
            fontSize=14,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#5c6ac4'),
            spaceAfter=8
        )

        subheading_style = ParagraphStyle(
            'Subheading',
            parent=styles['Heading3'],
            fontSize=12,
            fontName='Helvetica-Bold',
            spaceAfter=6
        )

        normal_style = ParagraphStyle(
            'Normal',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica',
            spaceBefore=4,
            spaceAfter=4
        )

        bold_style = ParagraphStyle(
            'Bold',
            parent=normal_style,
            fontName='Helvetica-Bold'
        )

        # Content elements for the PDF
        elements = []

        # Add header with date
        header_data = [
            ["EXPENSE REPORT", ""],
            ["", f"Date: {datetime.datetime.now().strftime('%d.%m.%Y')}"]
        ]

        header_table = Table(header_data, colWidths=[doc.width * 0.7, doc.width * 0.3])
        header_table.setStyle(TableStyle([
            ('FONT', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (0, 0), colors.HexColor('#0056b3')),
            ('FONT', (1, 1), (1, 1), 'Helvetica'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 1), (1, 1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (0, 0), 16),
            ('FONTSIZE', (1, 1), (1, 1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        elements.append(header_table)
        elements.append(Spacer(1, 12))

        # Add separator line
        separator = Table([['']], colWidths=[doc.width])
        separator.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, -1), 1, colors.HexColor('#5c6ac4')),
        ]))
        elements.append(separator)
        elements.append(Spacer(1, 12))

        # Add report title
        report_title = f"Expense Report"
        if category:
            report_title += f" - Category: {category}"
        elements.append(Paragraph(report_title, title_style))
        elements.append(Spacer(1, 6))

        # Add generation date
        elements.append(Paragraph(
            f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            normal_style
        ))
        elements.append(Spacer(1, 12))

        # Add a background box with report summary
        summary_text = []
        if not grouped_df.empty:
            total_amount = grouped_df['total_amount'].sum() if 'total_amount' in grouped_df.columns else 0
            transaction_count = grouped_df['transaction_count'].sum() if 'transaction_count' in grouped_df.columns else 0

            period_text = "All time"
            if 'period_label' in grouped_df.columns and not grouped_df.empty:
                # Konwersja do formatu sortowanego chronologicznie
                periods = grouped_df['period_label'].tolist()

                # Funkcja pomocnicza do konwersji period_label na wartość sortowaną
                def period_to_sortable(period):
                    if '-' in period:
                        parts = period.split('-')
                        if len(parts) == 2:  # Format YYYY-WW (rok-tydzień)
                            year, week = parts
                            # Upewnij się, że tydzień ma dwie cyfry dla poprawnego sortowania
                            return f"{year}-{int(week):02d}"
                    return period

                # Sortuj chronologicznie
                sorted_periods = sorted(periods, key=period_to_sortable)

                if sorted_periods:
                    first_period = sorted_periods[0]
                    last_period = sorted_periods[-1]
                    period_text = f"{first_period} to {last_period}"

            summary_text.append(["Period:", period_text])
            summary_text.append(["Total Expenses:", f"£{total_amount:.2f}"])
            summary_text.append(["Transaction Count:", f"{transaction_count}"])
            if category:
                summary_text.append(["Category:", f"{category}"])
        else:
            summary_text.append(["No data available for the selected criteria", ""])

        summary_table = Table(summary_text, colWidths=[doc.width * 0.3, doc.width * 0.7])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f5f9')),
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONT', (1, 0), (-1, -1), 'Helvetica'),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.white),
            ('BOX', (0, 0), (-1, -1), 0.25, colors.white),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))

        elements.append(summary_table)
        elements.append(Spacer(1, 20))

        # Add charts if available
        if chart_paths:
            elements.append(Paragraph("Expense Visualizations", heading_style))
            elements.append(Spacer(1, 0.1 * inch))

            for chart_name, chart_path in chart_paths.items():
                # Add chart title
                chart_title = chart_name.replace('_', ' ').title()
                elements.append(Paragraph(chart_title, subheading_style))

                try:
                    # Add chart image
                    img = Image(chart_path, width=450, height=300)
                    elements.append(img)
                    elements.append(Spacer(1, 0.25 * inch))
                except Exception as e:
                    elements.append(Paragraph(f"Could not load chart: {str(e)}", normal_style))

            elements.append(Spacer(1, 10))

        # Add summary data
        elements.append(Paragraph("Expense Summary", heading_style))
        elements.append(Spacer(1, 0.1 * inch))

        if not grouped_df.empty:
            # Convert DataFrame to list of lists for ReportLab table
            data = [grouped_df.columns.tolist()] + grouped_df.values.tolist()

            # Create table
            expense_table = Table(data)

            # Style the table
            table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#5c6ac4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#eeeeee')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')])
            ])

            # Apply the style to the table
            expense_table.setStyle(table_style)
            elements.append(expense_table)
        else:
            elements.append(Paragraph("No summary data available for the selected criteria", normal_style))

        elements.append(Spacer(1, 0.5 * inch))

        # Add detailed expenses (limit to 50 for PDF readability)
        max_records = 50
        elements.append(Paragraph("Detailed Expenses", heading_style))
        elements.append(Spacer(1, 0.1 * inch))

        if not detailed_df.empty:
            # Limit records for PDF
            if len(detailed_df) > max_records:
                elements.append(Paragraph(f"Showing first {max_records} of {len(detailed_df)} records",
                                        styles["Italic"]))
                detailed_df = detailed_df.head(max_records)

            # Convert DataFrame to list of lists for ReportLab table
            data = [detailed_df.columns.tolist()] + detailed_df.values.tolist()

            # Create table
            detailed_table = Table(data)

            # Style the table
            table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#5c6ac4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#eeeeee')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')])
            ])

            # Apply the style to the table
            detailed_table.setStyle(table_style)
            elements.append(detailed_table)
        else:
            elements.append(Paragraph("No detailed data available for the selected criteria", normal_style))

        elements.append(Spacer(1, inch))

        # Add footer
        footer_data = [[""], ["© Expense Tracker"]]
        footer_table = Table(footer_data, colWidths=[doc.width])
        footer_table.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#5c6ac4')),
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ('FONTSIZE', (0, 1), (-1, 1), 8),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.gray),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica'),
        ]))

        elements.append(footer_table)

        # Build the PDF document
        doc.build(elements)

        return pdf_path

    except Exception as e:
        logger.error(f"Error generating PDF report: {str(e)}", exc_info=True)
        raise


def send_report_email(category=None, start_date=None, end_date=None, recipient=None, format_type='excel'):
    """
    Generate and send an expense report via email with error handling and fallback options.

    Returns:
        dict: Status information including success flag and details
    """
    try:
        # Inicjalizacja konfiguracji i logowanie rozpoczęcia operacji
        config = Config()
        logger.info(
            f"Starting report generation: category={category}, period={start_date or 'all time'} to {end_date or 'present'}, format={format_type}")

        # Walidacja wejścia
        if format_type not in ['excel', 'pdf', 'csv']:
            logger.warning(f"Invalid format type '{format_type}' - defaulting to excel")
            format_type = 'excel'

        db_manager = get_db_connection(config)
        try:
            report_file, report_type, format_type = generate_report(
                db_manager=db_manager,
                category=category,
                start_date=start_date,
                end_date=end_date,
                group_by='month',
                format_type=format_type
            )
            logger.info(f"Report generated successfully: {report_file}")
        except Exception as report_error:
            logger.error(f"Report generation failed: {str(report_error)}", exc_info=True)
            return {
                'success': False,
                'stage': 'generation',
                'error': str(report_error)
            }

        # Ustalenie odbiorcy z failsafe
        recipient = recipient or config.DEFAULT_EMAIL_RECIPIENT
        if not recipient:
            logger.error("No recipient specified and no default recipient configured")
            return {'success': False, 'stage': 'preparation', 'error': 'No recipient specified'}

        # Przygotowanie e-maila z odpowiednią obsługą błędów
        try:
            # Użycie funkcji z module email_service do przygotowania i wysłania e-maila
            from app.services.email_service import send_email

            # Przygotowanie treści e-maila
            subject = f"Expense Report: {category or 'All Categories'}"
            body = f"""
            <html>
                <body>
                    <h2>Expense Report</h2>
                    <p>In the attachment you will find an expense report for category: <strong>{category or 'All Categories'}</strong>.</p>
                    <p>Date range: {start_date or 'All time'} - {end_date or 'Present'}</p>
                    <p>--<br>This is an automated message.</p>
                </body>
            </html>
            """

            # Weryfikacja czy plik istnieje przed próbą odczytu
            if not os.path.exists(report_file):
                logger.error(f"Report file does not exist: {report_file}")
                return {'success': False, 'stage': 'attachment', 'error': 'Report file not found'}

            # Odczyt pliku z obsługą błędów
            try:
                with open(report_file, 'rb') as f:
                    file_content = f.read()
            except (IOError, PermissionError) as file_error:
                logger.error(f"Could not read report file: {str(file_error)}", exc_info=True)
                return {'success': False, 'stage': 'file_reading', 'error': str(file_error)}

            # Wysłanie e-maila z wykorzystaniem modułu email_service z obsługą błędów SMTP
            email_result = send_email(
                recipient=recipient,
                subject=subject,
                body=body,
                attachments={os.path.basename(report_file): file_content}
            )

            if not email_result:
                # Spróbuj alternatywne metody wysyłki - implementacja strategii alternatywnych
                logger.warning("Primary email sending method failed, trying alternative method")
                email_result = _send_email_alternative(recipient, subject, body, report_file)

            if email_result:
                logger.info(f"Report email sent successfully to {recipient}")
                return {'success': True, 'recipient': recipient, 'report_file': report_file}
            else:
                logger.error(f"All email sending methods failed for recipient {recipient}")
                return {'success': False, 'stage': 'sending', 'error': 'Email sending failed'}

        except Exception as email_error:
            logger.error(f"Error preparing or sending email: {str(email_error)}", exc_info=True)
            return {'success': False, 'stage': 'email_preparation', 'error': str(email_error)}

    except Exception as e:
        logger.error(f"Unexpected error in send_report_email: {str(e)}", exc_info=True)
        return {'success': False, 'stage': 'unexpected', 'error': str(e)}


def _send_email_alternative(recipient, subject, body, attachment_path):
    """
    Alternatywna metoda wysyłania e-maila - używana gdy główna metoda zawiedzie.
    Może używać innego portu SMTP, innego serwera lub innej metody uwierzytelnienia.

    Returns:
        bool: True jeśli udało się wysłać e-mail, False w przeciwnym wypadku
    """
    try:
        config = Config()

        # Przygotowanie wiadomości
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = config.EMAIL_SENDER
        msg['To'] = recipient
        msg.attach(MIMEText(body, 'html'))

        # Dołącz załącznik
        with open(attachment_path, 'rb') as file:
            attachment = MIMEApplication(file.read())
            attachment.add_header(
                'Content-Disposition',
                'attachment',
                filename=os.path.basename(attachment_path)
            )
            msg.attach(attachment)

        # Alternatywna metoda - próba połączenia przez SSL zamiast TLS
        try:
            with smtplib.SMTP_SSL(config.SMTP_SERVER, 465, timeout=10) as server:
                server.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
                server.send_message(msg)
                logger.info(f"Alternative method (SSL) succeeded for {recipient}")
                return True
        except Exception as ssl_error:
            logger.warning(f"SSL method failed: {str(ssl_error)}")

            # Spróbuj inny serwer jako ostateczność
            backup_server = config.BACKUP_SMTP_SERVER if hasattr(config, 'BACKUP_SMTP_SERVER') else None
            if backup_server:
                try:
                    with smtplib.SMTP(backup_server, config.SMTP_PORT, timeout=10) as server:
                        server.starttls()
                        server.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
                        server.send_message(msg)
                        logger.info(f"Backup server method succeeded for {recipient}")
                        return True
                except Exception as backup_error:
                    logger.error(f"Backup server method failed: {str(backup_error)}")

        return False

    except Exception as e:
        logger.error(f"Alternative email sending method failed: {str(e)}", exc_info=True)
        return False

class DBContextManager:
    """Context manager wrapper for DBManager"""

    def __init__(self, config):
        self.config = config
        self.db_manager = None

    def __enter__(self):
        """Initialize and return DBManager instance"""
        self.db_manager = DBManager(
            host=self.config.DB_HOST,
            user=self.config.DB_USER,
            password=self.config.DB_PASSWORD,
            database=self.config.DB_NAME
        )
        return self.db_manager

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources if needed"""
        # Currently DBManager doesn't need explicit cleanup
        pass

# Funkcja get_db_connection bez żadnych klas - zwraca normalny DBManager
def get_db_connection(config):
    return DBManager(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME
    )
